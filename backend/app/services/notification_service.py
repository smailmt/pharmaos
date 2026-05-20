"""
Service notifications WhatsApp / SMS via Twilio.

Twilio est leader, supporte WhatsApp Business API. Pour le Maroc :
- SMS via Twilio fonctionne (numéros marocains supportés)
- WhatsApp via Twilio nécessite un sandbox au début puis approval Meta

Si TWILIO_* manquent, on tombe en mode "preview" : on ne fait pas l'envoi,
on retourne juste le payload qui aurait été envoyé. Très pratique pour les démos.
"""
from typing import Literal
from app.core.config import settings


class NotificationService:
    """Envoie SMS et WhatsApp via Twilio."""

    def __init__(self):
        self.twilio_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None) or ""
        self.twilio_token = getattr(settings, "TWILIO_AUTH_TOKEN", None) or ""
        self.twilio_from_sms = getattr(settings, "TWILIO_FROM_SMS", None) or ""
        self.twilio_from_whatsapp = getattr(settings, "TWILIO_FROM_WHATSAPP", None) or ""
        self.configured = bool(self.twilio_sid and self.twilio_token)

    async def send(
        self,
        to: str,
        body: str,
        channel: Literal["sms", "whatsapp"] = "sms",
    ) -> dict:
        """
        Envoie un message. Retourne {sent: bool, channel, to, body, sid?, error?}.
        En mode preview (sans config Twilio), `sent` = False mais l'opération réussit.
        """
        # Normalise le numéro : +212XXX pour le Maroc
        to_clean = to.strip().replace(" ", "")
        if not to_clean.startswith("+"):
            # Hypothèse Maroc : 06XX → +2126XX, 07XX → +2127XX
            if to_clean.startswith("0"):
                to_clean = "+212" + to_clean[1:]
            else:
                to_clean = "+212" + to_clean

        if not self.configured:
            # Mode preview
            return {
                "sent": False,
                "preview": True,
                "channel": channel,
                "to": to_clean,
                "body": body,
                "note": "Twilio non configuré — mode preview. Renseignez TWILIO_* dans .env pour activer.",
            }

        try:
            # Import lazy pour éviter dépendance dure
            try:
                from twilio.rest import Client as TwilioClient
            except ImportError:
                return {
                    "sent": False,
                    "channel": channel,
                    "to": to_clean,
                    "body": body,
                    "error": "Le package twilio n'est pas installé (pip install twilio)",
                }

            client = TwilioClient(self.twilio_sid, self.twilio_token)
            if channel == "whatsapp":
                if not self.twilio_from_whatsapp:
                    return {
                        "sent": False,
                        "channel": channel,
                        "to": to_clean,
                        "body": body,
                        "error": "TWILIO_FROM_WHATSAPP non configuré",
                    }
                msg = client.messages.create(
                    body=body,
                    from_=f"whatsapp:{self.twilio_from_whatsapp}",
                    to=f"whatsapp:{to_clean}",
                )
            else:  # sms
                if not self.twilio_from_sms:
                    return {
                        "sent": False,
                        "channel": channel,
                        "to": to_clean,
                        "body": body,
                        "error": "TWILIO_FROM_SMS non configuré",
                    }
                msg = client.messages.create(
                    body=body,
                    from_=self.twilio_from_sms,
                    to=to_clean,
                )

            return {
                "sent": True,
                "channel": channel,
                "to": to_clean,
                "body": body,
                "sid": msg.sid,
            }

        except Exception as e:
            return {
                "sent": False,
                "channel": channel,
                "to": to_clean,
                "body": body,
                "error": str(e),
            }


def build_credit_reminder_message(
    pharmacy_name: str,
    client_name: str,
    amount_due: str,
    days_overdue: int | None = None,
) -> str:
    """Compose un message de relance crédit poli (français)."""
    base = (
        f"Bonjour {client_name},\n\n"
        f"Nous vous rappelons qu'un solde de {amount_due} MAD reste dû "
        f"à {pharmacy_name}."
    )
    if days_overdue and days_overdue > 0:
        base += f" Cette échéance est en retard de {days_overdue} jour{'s' if days_overdue > 1 else ''}."
    base += (
        "\n\nMerci de passer régulariser dès que possible.\n"
        f"Cordialement,\n{pharmacy_name}"
    )
    return base
