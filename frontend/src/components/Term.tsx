/**
 * Glossaire métier — explique les abréviations en un seul endroit.
 * Utiliser <Term code="ICE" /> pour afficher le terme avec tooltip d'explication.
 */
import { useState } from "react";
import { HelpCircle } from "lucide-react";

export const GLOSSARY: Record<string, string> = {
  // Identifiants administratifs marocains
  ICE: "Identifiant Commun de l'Entreprise — 15 chiffres, identifie chaque entité commerciale au Maroc auprès de l'administration fiscale, douanière, sociale.",
  IF: "Identifiant Fiscal — numéro attribué par la DGI pour les déclarations fiscales (IS/IR/TVA).",
  RC: "Registre du Commerce — numéro d'inscription au tribunal, identifie l'entreprise comme entité juridique.",
  CNSS: "Caisse Nationale de Sécurité Sociale — affiliation pour les salariés (couverture sociale, AMO).",
  INPE: "Identifiant National des Professionnels Exerçants — registre des professionnels de santé au Maroc.",
  CIN: "Carte d'Identité Nationale — pièce d'identité marocaine.",
  AMO: "Assurance Maladie Obligatoire — régime de couverture santé géré par la CNSS/CNOPS.",
  CNOPS: "Caisse Nationale des Organismes de Prévoyance Sociale — couverture santé des fonctionnaires.",
  RAMED: "Régime d'Assistance Médicale aux Économiquement Démunis — couverture santé pour personnes sans ressources.",

  // Pharmacie / Commerce
  PPV: "Prix Public de Vente — prix de vente affiché au patient, TTC, fixé par le ministère pour les médicaments remboursables.",
  PPH: "Prix Public Hôpital — prix appliqué dans les hôpitaux publics.",
  PA: "Prix d'Achat — coût d'achat HT du produit chez le grossiste ou laboratoire.",
  "P/Q": "Prix unitaire / Quantité — couple prix-quantité utilisé pour les rectifications de prix.",
  BL: "Bon de Livraison — document accompagnant la livraison physique d'une commande.",
  BC: "Bon de Commande — document officiel pour passer une commande auprès d'un fournisseur.",
  BR: "Bon de Réception — document confirmant la réception et la conformité d'une livraison.",
  DCI: "Dénomination Commune Internationale — nom scientifique de la molécule active (ex: paracétamol = DCI pour Doliprane).",
  TVA: "Taxe sur la Valeur Ajoutée — au Maroc : 7% pour les médicaments, 20% pour la parapharmacie.",
  HT: "Hors Taxes — montant sans TVA.",
  TTC: "Toutes Taxes Comprises — montant final payé par le client.",

  // Comptabilité caisse
  "Z-report": "Rapport de clôture caisse fin de journée — totaux figés, ne peut plus être modifié.",
  Clôture: "Action de figer les ventes d'une journée. Aucune modification possible après.",

  // Tiers payants
  "Tiers payant": "Système où le patient ne paie que sa part, le reste est facturé directement à l'organisme (CNSS, CNOPS, mutuelle).",
  Bordereau: "Document récapitulatif envoyé à un tiers payeur regroupant plusieurs prescriptions.",

  // Stock
  Lot: "Numéro de lot fabricant — permet la traçabilité et le rappel de batch en cas de problème.",
  Péremption: "Date limite d'utilisation/vente d'un médicament.",
  Inventaire: "Comptage physique du stock pour aligner stock théorique et stock réel.",

  // Listes médicamenteuses
  "Liste I": "Médicaments à prescription obligatoire — soumis à ordonnance médicale, conservation dans armoire fermée.",
  "Liste II": "Médicaments à prescription obligatoire, moins restrictifs que Liste I.",
};

export function Term({ code, children }: { code: string; children?: React.ReactNode }) {
  const explanation = GLOSSARY[code];
  const [open, setOpen] = useState(false);

  if (!explanation) {
    return <>{children ?? code}</>;
  }

  return (
    <span className="relative inline-flex items-center gap-0.5 group">
      <span className="border-b border-dotted border-muted-foreground cursor-help">
        {children ?? code}
      </span>
      <button
        onClick={() => setOpen((o) => !o)}
        onBlur={() => setOpen(false)}
        className="text-muted-foreground hover:text-foreground opacity-50 group-hover:opacity-100"
        aria-label={`Explication de ${code}`}
      >
        <HelpCircle className="h-3 w-3" />
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-0 top-full mt-1 z-50 w-64 p-2.5 bg-popover border rounded-md shadow-lg text-xs leading-relaxed text-foreground"
        >
          <strong className="block text-foreground">{code}</strong>
          <span className="text-muted-foreground">{explanation}</span>
        </span>
      )}
    </span>
  );
}
