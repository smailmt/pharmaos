import { create } from "zustand";
import type { Product } from "@/types/api";

export interface CartItem {
  product: Product;
  quantity: number;
  unit_price_ttc: number; // modifiable au cas par cas
  discount_rate: number;  // 0..1
}

interface CartState {
  items: CartItem[];
  clientId: string | null;
  clientName: string | null;
  hasPrescription: boolean;
  prescriptionNumber: string | null;
  thirdPartyPayerId: string | null;
  addProduct: (p: Product) => void;
  updateQuantity: (productId: string, qty: number) => void;
  updatePrice: (productId: string, price: number) => void;
  updateDiscount: (productId: string, rate: number) => void;
  removeItem: (productId: string) => void;
  removeProduct: (productId: string) => void;
  setClient: (id: string | null, name?: string | null) => void;
  setPrescription: (has: boolean, number: string | null) => void;
  setThirdPartyPayer: (id: string | null) => void;
  clear: () => void;
  total: () => number;
}

export const useCart = create<CartState>((set, get) => ({
  items: [],
  clientId: null,
  clientName: null,
  hasPrescription: false,
  prescriptionNumber: null,
  thirdPartyPayerId: null,
  addProduct: (p) =>
    set((s) => {
      const existing = s.items.find((i) => i.product.id === p.id);
      if (existing) {
        return {
          items: s.items.map((i) =>
            i.product.id === p.id ? { ...i, quantity: i.quantity + 1 } : i
          ),
        };
      }
      return {
        items: [
          ...s.items,
          {
            product: p,
            quantity: 1,
            unit_price_ttc: parseFloat(p.sale_price_ttc),
            discount_rate: 0,
          },
        ],
      };
    }),
  updateQuantity: (productId, qty) =>
    set((s) => ({
      items: s.items.map((i) =>
        i.product.id === productId ? { ...i, quantity: Math.max(1, qty) } : i
      ),
    })),
  updatePrice: (productId, price) =>
    set((s) => ({
      items: s.items.map((i) =>
        i.product.id === productId ? { ...i, unit_price_ttc: Math.max(0, price) } : i
      ),
    })),
  updateDiscount: (productId, rate) =>
    set((s) => ({
      items: s.items.map((i) =>
        i.product.id === productId
          ? { ...i, discount_rate: Math.max(0, Math.min(1, rate)) }
          : i
      ),
    })),
  removeItem: (productId) =>
    set((s) => ({ items: s.items.filter((i) => i.product.id !== productId) })),
  removeProduct: (productId) =>
    set((s) => ({ items: s.items.filter((i) => i.product.id !== productId) })),
  setClient: (id, name = null) => set({ clientId: id, clientName: name }),
  setPrescription: (has, number) =>
    set({ hasPrescription: has, prescriptionNumber: number }),
  setThirdPartyPayer: (id) => set({ thirdPartyPayerId: id }),
  clear: () =>
    set({
      items: [],
      clientId: null,
      clientName: null,
      hasPrescription: false,
      prescriptionNumber: null,
      thirdPartyPayerId: null,
    }),
  total: () => {
    return get().items.reduce(
      (sum, i) => sum + i.quantity * i.unit_price_ttc * (1 - i.discount_rate),
      0
    );
  },
}));
