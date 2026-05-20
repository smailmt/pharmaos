"""Seed : données démo pour démarrer rapidement.

Usage : python -m app.scripts.seed
"""
import asyncio
from datetime import date, timedelta
from decimal import Decimal

from app.db.session import AsyncSessionLocal
from app.core.security import hash_password
from app.models.pharmacy import Pharmacy
from app.models.user import User
from app.models.product import Product, ProductLot
from app.models.client import Client
from app.models.supplier import Supplier
from app.models.third_party import ThirdPartyPayer


async def seed():
    async with AsyncSessionLocal() as db:
        # Pharmacie démo
        pharmacy = Pharmacy(
            name="Pharmacie Atlas",
            legal_name="Pharmacie Atlas SARL",
            ice="001234567890123",
            if_number="12345678",
            rc_number="123456",
            city="Casablanca",
            address="123 Bd Mohammed V",
            phone="+212 522 000 000",
            email="contact@pharmacieatlas.ma",
            pharmacist_in_charge="Dr. Salma Bennani",
            inpe_number="A123456",
            plan="pro",
        )
        db.add(pharmacy)
        await db.flush()

        # Utilisateur owner
        user = User(
            pharmacy_id=pharmacy.id,
            email="demo@pharmaos.ma",
            full_name="Dr. Salma Bennani",
            hashed_password=hash_password("demo1234"),
            role="owner",
        )
        db.add(user)

        # Produits
        products_data = [
            ("DOLI500", "3400930000010", "Doliprane 500mg", "Paracétamol", "Sanofi", "Comprimé", "500mg", Decimal("3.50"), Decimal("12.00"), 50, 100, False),
            ("AUGM1G", "3400930000020", "Augmentin 1g", "Amoxicilline + Acide clavulanique", "GSK", "Comprimé", "1g", Decimal("25.00"), Decimal("85.00"), 20, 50, True),
            ("EFFER500", "3400930000030", "Efferalgan 500mg", "Paracétamol", "UPSA", "Comprimé effervescent", "500mg", Decimal("4.20"), Decimal("15.00"), 30, 80, False),
            ("VOLT50", "3400930000040", "Voltarène 50mg", "Diclofénac", "Novartis", "Comprimé", "50mg", Decimal("8.50"), Decimal("28.00"), 30, 60, True),
            ("OMEP20", "3400930000050", "Omeprazole 20mg", "Omeprazole", "Sandoz", "Gélule", "20mg", Decimal("12.00"), Decimal("42.00"), 20, 50, True),
            ("VENTO", "3400930000060", "Ventoline", "Salbutamol", "GSK", "Aérosol", "100µg", Decimal("18.00"), Decimal("48.00"), 10, 30, True),
            ("ASP500", "3400930000070", "Aspirine 500mg", "Acide acétylsalicylique", "Bayer", "Comprimé", "500mg", Decimal("3.00"), Decimal("10.00"), 50, 100, False),
            ("INSUL", "3400930000080", "Insuline NovoRapid", "Insuline aspart", "Novo Nordisk", "Stylo", "100UI/ml", Decimal("85.00"), Decimal("145.00"), 5, 20, True),
        ]
        product_ids = []
        for code, barcode, name, dci, lab, form, dosage, ppa, ppv, smin, smax, prescription in products_data:
            p = Product(
                pharmacy_id=pharmacy.id,
                code=code, barcode=barcode, name=name, dci=dci, laboratory=lab,
                form=form, dosage=dosage,
                purchase_price_ht=ppa, sale_price_ttc=ppv,
                stock_min=smin, stock_max=smax,
                is_prescription_required=prescription,
                stock_quantity=0,  # sera mis à jour par les lots
            )
            db.add(p)
            await db.flush()
            product_ids.append(p.id)

            # 1 lot de démo par produit
            lot = ProductLot(
                pharmacy_id=pharmacy.id,
                product_id=p.id,
                lot_number=f"LOT-{code}-2026",
                quantity=80,
                expiration_date=date.today() + timedelta(days=540),
                purchase_price_ht=ppa,
                sale_price_ttc=ppv,  # PPV imprimé sur la boîte de ce lot
            )
            db.add(lot)
            p.stock_quantity = 80

        # Tiers payants (organismes typiques au Maroc — à titre de DEMO uniquement,
        # 100% modifiable par le pharmacien)
        payers_data = [
            ("CNSS", "Caisse Nationale de Sécurité Sociale", "public", Decimal("0.70"), 60, {"requires_prescription": True}),
            ("CNOPS", "Caisse Nationale des Organismes de Prévoyance Sociale", "public", Decimal("0.80"), 60, {"requires_prescription": True}),
            ("RAMED", "Régime d'Assistance Médicale", "public", Decimal("1.00"), 90, {"reimbursable_products_only": True}),
            ("MUTUELLE-X", "Mutuelle privée X", "mutual", Decimal("0.85"), 30, {}),
        ]
        payer_ids = []
        for code, name, type_, rate, terms, rules in payers_data:
            payer = ThirdPartyPayer(
                pharmacy_id=pharmacy.id,
                code=code, name=name, type=type_,
                default_coverage_rate=rate,
                payment_terms_days=terms,
                rules=rules,
                bordereau_frequency="monthly",
            )
            db.add(payer)
            await db.flush()
            payer_ids.append(payer.id)

        # Clients démo
        clients_data = [
            ("Ahmed El Idrissi", "+212 661 111 111", "AB123456", True, Decimal("2000"), payer_ids[0]),
            ("Fatima Zahra Alami", "+212 661 222 222", "CD234567", True, Decimal("3000"), payer_ids[1]),
            ("Mohammed Tahiri", "+212 661 333 333", "EF345678", False, Decimal("0"), None),
            ("Aïcha Bouazzaoui", "+212 661 444 444", "GH456789", True, Decimal("1500"), payer_ids[3]),
        ]
        for name, phone, cin, credit_enabled, limit, payer_id in clients_data:
            c = Client(
                pharmacy_id=pharmacy.id,
                full_name=name, phone=phone, cin=cin,
                credit_enabled=credit_enabled,
                credit_limit=limit,
                default_payment_terms_days=30,
                third_party_payer_id=payer_id,
            )
            db.add(c)

        # Fournisseurs
        suppliers_data = [
            ("COOP-PHARMA", "Cooperpharma", "wholesaler", "001234567890456", 30, Decimal("0.02")),
            ("SOPHA", "Sophadis", "wholesaler", "001234567890789", 45, Decimal("0.03")),
            ("SANOFI", "Sanofi Maroc", "laboratory", "001234567891012", 60, Decimal("0")),
        ]
        for code, name, type_, ice, terms, discount in suppliers_data:
            s = Supplier(
                pharmacy_id=pharmacy.id,
                code=code, name=name, type=type_,
                ice=ice,
                payment_terms_days=terms,
                default_discount_rate=discount,
                city="Casablanca",
            )
            db.add(s)

        await db.commit()
        print(f"✅ Seed terminé : pharmacie {pharmacy.name}")
        print(f"   Login : demo@pharmaos.ma / demo1234")


if __name__ == "__main__":
    asyncio.run(seed())
