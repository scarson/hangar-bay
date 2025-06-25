/**
 * Represents the query parameters for fetching ship contracts.
 * Aligns with the backend API's query parameters.
 */
export interface ShipContractsRequestParams {
  page?: number;
  size?: number;
  region_id?: number;
  ship_type_id?: number;
}

/**
 * Represents a single ship contract, aligning with the backend's ShipContractRead schema.
 */
export interface ShipContract {
  contract_id: number;
  ship_type_id: number;
  ship_name: string;
  price: number;
  location_name: string;
  date_issued: string; // ISO 8601 date string
  title: string;
  is_blueprint_copy: boolean;
  quantity: number;
  runs?: number | null;
  material_efficiency?: number | null;
  time_efficiency?: number | null;
  contains_additional_items: boolean;
}

/**
 * Represents the paginated response for ship contracts from the backend.
 */
export interface PaginatedShipContractsResponse {
  items: ShipContract[];
  total_items: number;
  total_pages: number;
  page: number;
  size: number;
}
