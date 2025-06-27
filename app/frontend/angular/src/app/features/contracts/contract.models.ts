/**
 * Represents an item within a public contract, mirroring the backend's ContractItemSchema.
 */
export interface ContractItem {
  record_id: number;
  type_id: number;
  quantity: number;
  is_included: boolean;
  is_singleton: boolean;
  raw_quantity?: number;
  type_name?: string;
  category?: string;
  market_group_id?: number;
}

/**
 * Represents a public contract, mirroring the backend's ContractSchema.
 */
export interface Contract {
  contract_id: number;
  issuer_id: number;
  issuer_corporation_id: number;
  start_location_id: number;
  end_location_id?: number;
  type: string;
  status: string;
  title?: string;
  for_corporation: boolean;
  date_issued: string; // ISO 8601 date string
  date_expired: string; // ISO 8601 date string
  date_completed?: string; // ISO 8601 date string
  price?: number;
  reward?: number;
  volume?: number;
  start_location_name?: string;
  issuer_name?: string;
  issuer_corporation_name?: string;
  is_ship_contract: boolean;
  items: ContractItem[];
}

/**
 * Represents the structure of a paginated API response for contracts,
 * mirroring the backend's PaginatedContractResponse.
 */
export interface PaginatedContractsResponse {
  total: number;
  page: number;
  size: number;
  items: Contract[];
}

/**
 * Defines the structure for the contract search filters.
 * This aligns with the query parameters of the `list_public_contracts` backend endpoint.
 */
export interface ContractSearchFilters {
  page: number;
  size: number;
  search?: string;
  type?: string;
  sort?: string;
  order?: 'asc' | 'desc';
}
