/**
 * IndexedDB wrapper pour mode offline.
 *
 * Deux stores :
 * - `products` : snapshot du catalogue (lecture offline pour la caisse)
 * - `pending_sales` : ventes créées hors-ligne, à synchroniser au retour
 */
import { openDB, type DBSchema, type IDBPDatabase } from "idb";
import type { Product, SaleCreate } from "@/types/api";

interface PharmaOSDB extends DBSchema {
  products: {
    key: string; // product id
    value: Product;
    indexes: { "by-barcode": string; "by-code": string };
  };
  pending_sales: {
    key: string; // local uuid
    value: {
      id: string;
      created_at: number;
      payload: SaleCreate;
      attempts: number;
      last_error: string | null;
      status: "pending" | "synced" | "failed";
    };
    indexes: { "by-status": string };
  };
  meta: {
    key: string;
    value: { key: string; value: unknown; updated_at: number };
  };
}

let dbPromise: Promise<IDBPDatabase<PharmaOSDB>> | null = null;

function getDB() {
  if (!dbPromise) {
    dbPromise = openDB<PharmaOSDB>("pharmaos", 1, {
      upgrade(db) {
        const productsStore = db.createObjectStore("products", { keyPath: "id" });
        productsStore.createIndex("by-barcode", "barcode");
        productsStore.createIndex("by-code", "code");

        const salesStore = db.createObjectStore("pending_sales", { keyPath: "id" });
        salesStore.createIndex("by-status", "status");

        db.createObjectStore("meta", { keyPath: "key" });
      },
    });
  }
  return dbPromise;
}

// ============ Products cache ============
export async function cacheProducts(products: Product[]): Promise<void> {
  const db = await getDB();
  const tx = db.transaction("products", "readwrite");
  await tx.objectStore("products").clear();
  await Promise.all(products.map((p) => tx.objectStore("products").put(p)));
  await tx.done;
  await setMeta("products_cached_at", Date.now());
}

export async function getCachedProducts(): Promise<Product[]> {
  const db = await getDB();
  return db.getAll("products");
}

export async function getCachedProductByBarcode(barcode: string): Promise<Product | undefined> {
  const db = await getDB();
  return db.getFromIndex("products", "by-barcode", barcode);
}

// ============ Pending sales queue ============
export interface PendingSale {
  id: string;
  created_at: number;
  payload: SaleCreate;
  attempts: number;
  last_error: string | null;
  status: "pending" | "synced" | "failed";
}

export async function queuePendingSale(payload: SaleCreate): Promise<PendingSale> {
  const db = await getDB();
  const entry: PendingSale = {
    id: `local_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    created_at: Date.now(),
    payload,
    attempts: 0,
    last_error: null,
    status: "pending",
  };
  await db.put("pending_sales", entry);
  return entry;
}

export async function listPendingSales(): Promise<PendingSale[]> {
  const db = await getDB();
  return db.getAllFromIndex("pending_sales", "by-status", "pending");
}

export async function listAllSales(): Promise<PendingSale[]> {
  const db = await getDB();
  return db.getAll("pending_sales");
}

export async function markSaleSynced(id: string): Promise<void> {
  const db = await getDB();
  const entry = await db.get("pending_sales", id);
  if (entry) {
    entry.status = "synced";
    await db.put("pending_sales", entry);
  }
}

export async function markSaleFailed(id: string, error: string): Promise<void> {
  const db = await getDB();
  const entry = await db.get("pending_sales", id);
  if (entry) {
    entry.attempts += 1;
    entry.last_error = error;
    // Après 5 tentatives, on marque failed (l'opérateur doit intervenir)
    if (entry.attempts >= 5) {
      entry.status = "failed";
    }
    await db.put("pending_sales", entry);
  }
}

export async function deleteSyncedSales(): Promise<number> {
  const db = await getDB();
  const synced = await db.getAllFromIndex("pending_sales", "by-status", "synced");
  await Promise.all(synced.map((s) => db.delete("pending_sales", s.id)));
  return synced.length;
}

// ============ Meta ============
export async function setMeta(key: string, value: unknown): Promise<void> {
  const db = await getDB();
  await db.put("meta", { key, value, updated_at: Date.now() });
}

export async function getMeta<T = unknown>(key: string): Promise<T | undefined> {
  const db = await getDB();
  const entry = await db.get("meta", key);
  return entry?.value as T | undefined;
}
