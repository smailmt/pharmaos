/**
 * Dialog "Vérifier interactions" — analyse les médicaments du panier
 * via Claude pour détecter interactions et contre-indications.
 */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Pill,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toast";

interface InteractionResult {
  summary: string;
  interactions: Array<{
    drugs?: string[];
    severity?: string;
    description?: string;
    recommendation?: string;
    [k: string]: unknown;
  }>;
  warnings: string[];
}

interface DrugInteractionsDialogProps {
  open: boolean;
  onClose: () => void;
  medications: string[];
}

export function DrugInteractionsDialog({
  open,
  onClose,
  medications,
}: DrugInteractionsDialogProps) {
  const [patientAge, setPatientAge] = useState("");
  const [conditions, setConditions] = useState("");
  const [result, setResult] = useState<InteractionResult | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<InteractionResult>(
        "/ai/interactions",
        {
          medications,
          patient_age: patientAge ? parseInt(patientAge) : null,
          patient_conditions: conditions
            ? conditions.split(",").map((s) => s.trim()).filter(Boolean)
            : null,
        },
        { timeout: 30_000 }
      );
      return data;
    },
    onSuccess: (data) => setResult(data),
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  const handleClose = () => {
    setResult(null);
    setPatientAge("");
    setConditions("");
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-primary" />
            Vérifier les interactions
            <Badge variant="secondary" className="text-[10px] ml-1">
              <Sparkles className="h-3 w-3 mr-0.5" />
              IA Claude
            </Badge>
          </DialogTitle>
          <DialogDescription>
            Analyse pharmaceutique des médicaments sélectionnés pour le marché marocain.
          </DialogDescription>
        </DialogHeader>

        {!result ? (
          <>
            <div className="space-y-3">
              <div>
                <Label className="text-xs">Médicaments à analyser ({medications.length})</Label>
                <div className="flex flex-wrap gap-1.5 mt-1.5 p-2 rounded-md bg-muted/30 border">
                  {medications.length === 0 ? (
                    <span className="text-xs text-muted-foreground italic">
                      Aucun médicament dans le panier.
                    </span>
                  ) : (
                    medications.map((m) => (
                      <Badge key={m} variant="outline" className="font-normal">
                        <Pill className="h-3 w-3 mr-1" />
                        {m}
                      </Badge>
                    ))
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">
                    Âge patient <span className="text-muted-foreground">(optionnel)</span>
                  </Label>
                  <Input
                    type="number"
                    value={patientAge}
                    onChange={(e) => setPatientAge(e.target.value)}
                    placeholder="Ex: 65"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">
                    Antécédents <span className="text-muted-foreground">(séparés par virgule)</span>
                  </Label>
                  <Input
                    value={conditions}
                    onChange={(e) => setConditions(e.target.value)}
                    placeholder="diabète, hypertension"
                  />
                </div>
              </div>

              <div className="bg-amber-50 border border-amber-200 rounded-md p-2.5 text-xs text-amber-900">
                <strong>Note :</strong> cette analyse est informative. Elle ne remplace pas la
                consultation des sources officielles (RCP, Vidal Maroc) ni l'avis médical.
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={handleClose}>
                Annuler
              </Button>
              <Button
                onClick={() => mutation.mutate()}
                disabled={medications.length === 0 || mutation.isPending}
              >
                {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Analyser
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <div className="space-y-4">
              {/* Résumé */}
              <div className="bg-primary/5 border border-primary/20 rounded-md p-3">
                <p className="text-xs font-semibold text-primary mb-1">Résumé</p>
                <p className="text-sm">{result.summary}</p>
              </div>

              {/* Interactions */}
              {result.interactions && result.interactions.length > 0 ? (
                <div>
                  <h3 className="text-sm font-semibold mb-2">
                    Interactions détectées ({result.interactions.length})
                  </h3>
                  <div className="space-y-2">
                    {result.interactions.map((interaction, i) => (
                      <InteractionCard key={i} interaction={interaction} />
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-2 p-3 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-900">
                  <CheckCircle2 className="h-5 w-5 shrink-0" />
                  <p className="text-sm">
                    Aucune interaction significative détectée entre ces médicaments.
                  </p>
                </div>
              )}

              {/* Warnings */}
              {result.warnings && result.warnings.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold mb-2 flex items-center gap-1">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    Points d'attention
                  </h3>
                  <ul className="space-y-1.5">
                    {result.warnings.map((w, i) => (
                      <li
                        key={i}
                        className="text-sm flex items-start gap-2 p-2 rounded bg-amber-50 border border-amber-200"
                      >
                        <span className="text-amber-700">•</span>
                        <span>{w}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setResult(null)}>
                Nouvelle analyse
              </Button>
              <Button onClick={handleClose}>Fermer</Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function InteractionCard({
  interaction,
}: {
  interaction: InteractionResult["interactions"][number];
}) {
  const sev = (interaction.severity || "").toLowerCase();
  const isHigh = sev.includes("majeur") || sev.includes("major") || sev.includes("grave") || sev.includes("contre");
  const isMod = sev.includes("modér") || sev.includes("moderate");

  const borderClass = isHigh
    ? "border-red-300 bg-red-50"
    : isMod
    ? "border-amber-300 bg-amber-50"
    : "border-slate-200 bg-slate-50";

  return (
    <div className={`rounded-md border p-3 ${borderClass}`}>
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="flex flex-wrap gap-1">
          {(interaction.drugs ?? []).map((d) => (
            <Badge key={d} variant="outline" className="text-[10px]">
              {d}
            </Badge>
          ))}
        </div>
        {interaction.severity && (
          <Badge
            variant={isHigh ? "destructive" : isMod ? "warning" : "secondary"}
            className="text-[10px] shrink-0"
          >
            {interaction.severity}
          </Badge>
        )}
      </div>
      {interaction.description && (
        <p className="text-sm leading-relaxed">{interaction.description}</p>
      )}
      {interaction.recommendation && (
        <p className="text-xs mt-1.5 italic text-muted-foreground">
          <strong>Recommandation :</strong> {interaction.recommendation}
        </p>
      )}
    </div>
  );
}
