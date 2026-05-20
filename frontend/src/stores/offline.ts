import { create } from "zustand";
import { api } from "@/lib/api";
import {
  listPendingSales,
  markSaleSynced,
  markSaleFailed,
  deleteSyncedSales,
  type PendingSale,
} from "@/lib/offline-db";
import { toast } from "@/components/ui/toast";

interface OfflineState {
  online: boolean;
  syncing: boolean;
  pendingCount: number;
  failedCount: number;
  lastSyncAt: number | null;
  setOnline: (v: boolean) => void;
  refreshCounts: () => Promise<void>;
  syncNow: () => Promise<{ synced: number; failed: number }>;
}

export const useOffline = create<OfflineState>((set, get) => ({
  online: typeof navigator !== "undefined" ? navigator.onLine : true,
  syncing: false,
  pendingCount: 0,
  failedCount: 0,
  lastSyncAt: null,

  setOnline: (v) => {
    const wasOffline = !get().online;
    set({ online: v });
    if (v && wasOffline) {
      // Retour en ligne : sync auto
      get().syncNow().catch(() => undefined);
    }
  },

  refreshCounts: async () => {
    const all = await listPendingSales();
    set({ pendingCount: all.length });
  },

  syncNow: async () => {
    if (get().syncing) return { synced: 0, failed: 0 };
    set({ syncing: true });
    let synced = 0;
    let failed = 0;
    try {
      const pending = await listPendingSales();
      for (const entry of pending) {
        try {
          await api.post("/sales", entry.payload, { timeout: 10_000 });
          await markSaleSynced(entry.id);
          synced++;
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : String(err);
          await markSaleFailed(entry.id, msg);
          failed++;
        }
      }
      // Nettoyer les synced après un délai (pour que l'utilisateur voie le succès)
      if (synced > 0) {
        setTimeout(() => {
          deleteSyncedSales().catch(() => undefined);
        }, 5000);
      }
      set({ lastSyncAt: Date.now() });
      if (synced > 0) {
        toast.success(
          `${synced} vente${synced > 1 ? "s" : ""} synchronisée${synced > 1 ? "s" : ""}`,
          failed > 0 ? `${failed} échec${failed > 1 ? "s" : ""}, à retenter` : undefined
        );
      } else if (failed > 0) {
        toast.error(`${failed} vente${failed > 1 ? "s" : ""} en échec`);
      }
    } finally {
      await get().refreshCounts();
      set({ syncing: false });
    }
    return { synced, failed };
  },
}));

// Initialisation : écoute online/offline + 1er refresh
if (typeof window !== "undefined") {
  window.addEventListener("online", () => useOffline.getState().setOnline(true));
  window.addEventListener("offline", () => useOffline.getState().setOnline(false));
  // Refresh initial des compteurs
  useOffline.getState().refreshCounts().catch(() => undefined);
  // Sync périodique (toutes les 30s si en ligne et qu'il y a des pending)
  setInterval(() => {
    const st = useOffline.getState();
    if (st.online && !st.syncing && st.pendingCount > 0) {
      st.syncNow().catch(() => undefined);
    }
  }, 30_000);
}
