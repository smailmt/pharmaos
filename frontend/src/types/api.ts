// Types miroir des schémas Pydantic backend

export interface Product {
  id: string;
  pharmacy_id: string;
  code: string;
  barcode: string | null;
  name: string;
  dci: string | null;
  laboratory: string | null;
  form: string | null;
  dosage: string | null;
  category: string | null;
  purchase_price_ht: string;
  sale_price_ttc: string;
  vat_rate: string;
  stock_quantity: number;
  stock_min: number;
  stock_max: number;
  is_prescription_required: boolean;
  is_psychotropic: boolean;
  is_reimbursable: boolean;
  is_active: boolean;
  created_at: string;
}

export interface ProductLot {
  id: string;
  product_id: string;
  lot_number: string;
  quantity: number;
  expiration_date: string;
  purchase_price_ht: string | null;
  created_at: string;
}

export interface Client {
  id: string;
  pharmacy_id: string;
  code: string | null;
  full_name: string;
  phone: string | null;
  email: string | null;
  cin: string | null;
  birth_date: string | null;
  address: string | null;
  city: string | null;
  credit_enabled: boolean;
  credit_limit: string;
  default_payment_terms_days: number;
  third_party_payer_id: string | null;
  third_party_card_number: string | null;
  loyalty_points: number;
  risk_score: number;
  is_active: boolean;
  created_at: string;
}

export interface ClientDetail extends Client {
  current_balance: string;
  overdue_amount: string;
  available_credit: string;
  total_purchases: string;
  last_purchase_date: string | null;
}

export interface SaleItemIn {
  product_id: string;
  lot_id?: string | null;
  quantity: number;
  unit_price_ttc: string;
  discount_rate?: string;
}

export interface SaleItem {
  id: string;
  product_id: string;
  lot_id: string | null;
  quantity: number;
  unit_price_ttc: string;
  discount_rate: string;
  line_total_ttc: string;
  is_reimbursable: boolean;
}

export interface Sale {
  id: string;
  sale_number: string;
  sale_date: string;
  client_id: string | null;
  has_prescription: boolean;
  prescription_number: string | null;
  third_party_payer_id: string | null;
  third_party_coverage_rate: string | null;
  subtotal_ht: string;
  total_vat: string;
  total_discount: string;
  total_ttc: string;
  payer_share: string;
  client_share: string;
  paid_cash: string;
  paid_card: string;
  paid_check: string;
  paid_credit: string;
  payment_method: string;
  status: string;
  loyalty_points_earned: number;
  loyalty_points_used: number;
  items: SaleItem[];
  created_at: string;
}

export interface SaleCreate {
  client_id?: string | null;
  has_prescription?: boolean;
  prescription_number?: string | null;
  third_party_payer_id?: string | null;
  items: SaleItemIn[];
  paid_cash?: string;
  paid_card?: string;
  paid_check?: string;
  paid_credit?: string;
  total_discount?: string;
  notes?: string | null;
}

export interface ThirdPartyPayer {
  id: string;
  code: string;
  name: string;
  type: string;
  default_coverage_rate: string;
  payment_terms_days: number;
  is_active: boolean;
}

export interface AgingBucket {
  bucket: string;
  amount: string;
  clients_count: number;
}

export interface AgingReport {
  as_of_date: string;
  total_outstanding: string;
  buckets: AgingBucket[];
}
