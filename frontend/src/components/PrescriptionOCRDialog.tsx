import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Camera,
  Upload,
  Loader2,
  Sparkles,
  AlertTriangle,
  Check,
  FileImage,
  X,
} from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "@/components/ui/toast";
import type { Product } from "@/types/api";

interface PrescriptionLine {
  medication_name: string;
  dci: string | null;
  dosage: string | null;
  quantity: number | null;
  duration_days: number | null;
  instructions: string | null;
  confidence: "low" | "medium" | "high";
}

interface OCRResponse {
  raw_text: string;
  prescriber: string | null;
  prescription_date: string | null;
  patient_name: string | null;
  lines: PrescriptionLine[];
  warnings: string[];
}

interface PrescriptionOCRDialogProps {
  open: boolean;
  onClose: () => void;
  products: Product[];
  onAddLines: (productIds: string[]) => void;
}

export function PrescriptionOCRDialog({
  open,
  onClose,
  products,
  onAddLines,
}: PrescriptionOCRDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [result, setResult] = useState<OCRResponse | null>(null);
  const [selected, setSelected] = useState<Record<number, string | null>>({});

  const reset = () => {
    setImagePreview(null);
    setResult(null);
    setSelected({});
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleFile = async (file: File) => {
    if (!file.type.startsWith("image/")) {
      toast.error("Format invalide", "Veuillez sélectionner une image");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Image trop grande", "Maximum 5 MB");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      setImagePreview(result);
      ocrMutation.mutate({ dataUrl: result, mediaType: file.type });
    };
    reader.readAsDataURL(file);
  };

  const ocrMutation = useMutation({
    mutationFn: async ({ dataUrl, mediaType }: { dataUrl: string; mediaType: string }) => {
      const { data } = await api.post<OCRResponse>(
        "/ai/prescription-ocr",
        { image_base64: dataUrl, media_type: mediaType },
        { timeout: 60_000 } // Claude Vision peut prendre 15-30s
      );
      return data;
    },
    onSuccess: (data) => {
      setResult(data);
      // Pré-sélection : matcher les noms avec le catalogue par best-effort
      const initialSelected: Record<number, string | null> = {};
      data.lines.forEach((line, i) => {
        const term = (line.medication_name || line.dci || "").toLowerCase();
        if (!term) {
          initialSelected[i] = null;
          return;
        }
        const match = products.find(
          (p) =>
            p.name.toLowerCase().includes(term) ||
            (p.dci && p.dci.toLowerCase().includes(term))
        );
        initialSelected[i] = match?.id ?? null;
      });
      setSelected(initialSelected);
    },
    onError: (err) => toast.error("Échec OCR", extractErrorMessage(err)),
  });

  const handleAddToCart = () => {
    const ids = Object.values(selected).filter((v): v is string => !!v);
    if (ids.length === 0) {
      toast.error("Aucun produit sélectionné");
      return;
    }
    onAddLines(ids);
    handleClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Lecture d'ordonnance par IA
          </DialogTitle>
          <DialogDescription>
            Prenez une photo de l'ordonnance — l'IA extrait les médicaments et les pré-remplit dans le panier.
          </DialogDescription>
        </DialogHeader>

        {!imagePreview && (
          <div className="space-y-3">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full border-2 border-dashed border-input rounded-lg p-8 text-center hover:border-primary hover:bg-accent/30 transition-colors"
            >
              <FileImage className="h-10 w-10 mx-auto text-muted-foreground mb-2" />
              <p className="font-medium">Cliquez pour photographier ou importer</p>
              <p className="text-xs text-muted-foreground mt-1">
                JPG, PNG, WebP — max 5 MB
              </p>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFile(file);
              }}
            />
          </div>
        )}

        {imagePreview && (
          <div className="space-y-4">
            <div className="relative">
              <img
                src={imagePreview}
                alt="Ordonnance"
                className="max-h-48 w-full object-contain rounded-md border bg-muted"
              />
              <button
                onClick={reset}
                className="absolute top-2 right-2 bg-white rounded-full p-1 shadow"
                aria-label="Retirer l'image"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {ocrMutation.isPending && (
              <div className="flex items-center gap-3 bg-primary/5 border border-primary/20 rounded-md p-3">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
                <div>
                  <p className="text-sm font-medium">Analyse en cours…</p>
                  <p className="text-xs text-muted-foreground">
                    Claude Vision lit l'ordonnance et croise avec votre catalogue.
                  </p>
                </div>
              </div>
            )}

            {result && (
              <div className="space-y-3">
                {/* En-tête extraite */}
                {(result.prescriber || result.prescription_date || result.patient_name) && (
                  <div className="bg-muted/50 rounded-md p-3 text-sm space-y-1">
                    {result.patient_name && (
                      <div>
                        <span className="text-muted-foreground">Patient : </span>
                        <span className="font-medium">{result.patient_name}</span>
                      </div>
                    )}
                    {result.prescriber && (
                      <div>
                        <span className="text-muted-foreground">Prescripteur : </span>
                        <span>{result.prescriber}</span>
                      </div>
                    )}
                    {result.prescription_date && (
                      <div>
                        <span className="text-muted-foreground">Date : </span>
                        <span>{result.prescription_date}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Warnings */}
                {result.warnings.length > 0 && (
                  <div className="bg-amber-50 border border-amber-200 rounded-md p-3">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-700 mt-0.5 shrink-0" />
                      <div className="text-sm text-amber-900">
                        <p className="font-medium mb-1">À vérifier :</p>
                        <ul className="list-disc pl-4 space-y-0.5 text-xs">
                          {result.warnings.map((w, i) => (
                            <li key={i}>{w}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                )}

                {/* Lignes détectées */}
                <div>
                  <p className="text-sm font-medium mb-2">
                    Médicaments détectés ({result.lines.length})
                  </p>
                  {result.lines.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      Aucun médicament reconnu.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {result.lines.map((line, i) => (
                        <LineRow
                          key={i}
                          line={line}
                          products={products}
                          selectedProductId={selected[i] ?? null}
                          onSelect={(pid) =>
                            setSelected((s) => ({ ...s, [i]: pid }))
                          }
                        />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Annuler
          </Button>
          {result && result.lines.length > 0 && (
            <Button onClick={handleAddToCart}>
              <Check className="h-4 w-4 mr-1" />
              Ajouter au panier
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function LineRow({
  line,
  products,
  selectedProductId,
  onSelect,
}: {
  line: PrescriptionLine;
  products: Product[];
  selectedProductId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const confidenceColor = {
    high: "success" as const,
    medium: "secondary" as const,
    low: "warning" as const,
  }[line.confidence];

  return (
    <div className="border rounded-md p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-sm">
            {line.medication_name || <span className="italic text-muted-foreground">— non identifié —</span>}
          </p>
          <p className="text-xs text-muted-foreground">
            {[line.dci, line.dosage, line.instructions].filter(Boolean).join(" · ") || "Aucun détail"}
          </p>
          {(line.quantity || line.duration_days) && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {line.quantity && `${line.quantity} boîte(s)`}
              {line.quantity && line.duration_days && " · "}
              {line.duration_days && `${line.duration_days} jours`}
            </p>
          )}
        </div>
        <Badge variant={confidenceColor} className="text-[10px]">
          {line.confidence}
        </Badge>
      </div>
      <select
        value={selectedProductId ?? ""}
        onChange={(e) => onSelect(e.target.value || null)}
        className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <option value="">— Ne pas ajouter —</option>
        {products.map((p) => (
          <option key={p.id} value={p.id} disabled={p.stock_quantity <= 0}>
            {p.name}
            {p.stock_quantity <= 0 ? " (stock épuisé)" : ` (stock ${p.stock_quantity})`}
          </option>
        ))}
      </select>
    </div>
  );
}
