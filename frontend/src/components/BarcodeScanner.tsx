import { useEffect, useRef, useState } from "react";
import { BrowserMultiFormatReader, IScannerControls } from "@zxing/browser";
import { Camera, X, Loader2, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface BarcodeScannerProps {
  open: boolean;
  onClose: () => void;
  onScan: (text: string) => void;
}

export function BarcodeScanner({ open, onClose, onScan }: BarcodeScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const controlsRef = useRef<IScannerControls | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      // Stop scanner on close
      controlsRef.current?.stop();
      controlsRef.current = null;
      return;
    }

    let cancelled = false;

    const start = async () => {
      setError(null);
      setStarting(true);
      try {
        // Lister les caméras
        const allDevices = await BrowserMultiFormatReader.listVideoInputDevices();
        if (cancelled) return;
        setDevices(allDevices);

        // Préférence : caméra arrière (label contient "back" ou "environment")
        const preferred =
          allDevices.find((d) => /back|environment|arrière|rear/i.test(d.label)) ||
          allDevices[allDevices.length - 1] ||
          allDevices[0];

        const targetDeviceId = deviceId ?? preferred?.deviceId ?? undefined;
        setDeviceId(targetDeviceId ?? null);

        const reader = new BrowserMultiFormatReader();
        const controls = await reader.decodeFromVideoDevice(
          targetDeviceId,
          videoRef.current!,
          (result, err, ctl) => {
            if (cancelled) return;
            if (result) {
              const text = result.getText();
              onScan(text);
              ctl.stop();
              onClose();
            }
            // On ignore les NotFoundException (frame sans code) — zxing les émet en continu
          }
        );
        if (cancelled) {
          controls.stop();
          return;
        }
        controlsRef.current = controls;
      } catch (e: unknown) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : String(e);
          setError(`Impossible d'accéder à la caméra : ${msg}`);
        }
      } finally {
        if (!cancelled) setStarting(false);
      }
    };

    start();

    return () => {
      cancelled = true;
      controlsRef.current?.stop();
      controlsRef.current = null;
    };
  }, [open, deviceId, onScan, onClose]);

  const handleSwitchCamera = () => {
    if (devices.length < 2 || !deviceId) return;
    const currentIdx = devices.findIndex((d) => d.deviceId === deviceId);
    const next = devices[(currentIdx + 1) % devices.length];
    setDeviceId(next.deviceId);
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Camera className="h-5 w-5" />
            Scanner un code-barres
          </DialogTitle>
          <DialogDescription>
            Pointez la caméra vers le code-barres EAN-13 du produit.
          </DialogDescription>
        </DialogHeader>

        <div className="relative bg-black rounded-md overflow-hidden aspect-square">
          <video ref={videoRef} className="w-full h-full object-cover" playsInline muted />
          {starting && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/60">
              <Loader2 className="h-8 w-8 text-white animate-spin" />
            </div>
          )}
          {!starting && !error && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="w-3/4 h-1/3 border-2 border-emerald-400 rounded-md shadow-[0_0_0_2000px_rgba(0,0,0,0.4)]" />
            </div>
          )}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-900 rounded-md p-3 text-sm">
            {error}
            <p className="text-xs mt-1 text-red-700">
              Vérifiez que vous autorisez l'accès à la caméra et que vous êtes en HTTPS (ou localhost).
            </p>
          </div>
        )}

        <div className="flex gap-2">
          {devices.length > 1 && (
            <Button variant="outline" onClick={handleSwitchCamera} className="flex-1">
              <RotateCw className="h-4 w-4 mr-1" />
              Changer
            </Button>
          )}
          <Button variant="outline" onClick={onClose} className="flex-1">
            <X className="h-4 w-4 mr-1" />
            Fermer
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
