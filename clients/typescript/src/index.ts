export type JsonObject = Record<string, unknown>;

export interface VotingClientOptions {
  fetchImpl?: typeof fetch;
}

export interface AuditLogEntry {
  log_id: number;
  component: string;
  event_type: string;
  occurred_at: string;
  payload: JsonObject;
  prev_hash: string;
  log_hash: string;
}

export interface AuditLogPage {
  audit_log: AuditLogEntry[];
  has_more: boolean;
  next_after: number;
}

export interface LocalAuditVerifyValid {
  valid: true;
  total: number;
  head_hash: string;
}

export interface LocalAuditVerifyInvalid {
  valid: false;
  total: number;
  broken_at: number;
  broken_reason: "prev_hash_mismatch" | "log_hash_mismatch";
}

export type LocalAuditVerifyResult = LocalAuditVerifyValid | LocalAuditVerifyInvalid;

export declare class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly message: string;
}

export declare class ValueError extends Error {}

export declare class VotingClient {
  constructor(baseUrl: string, options?: VotingClientOptions);
  health(): Promise<JsonObject>;
  listElections(): Promise<JsonObject[]>;
  getElection(electionId: string): Promise<JsonObject>;
  bulletinBoard(electionId: string): Promise<JsonObject>;
  tally(electionId: string): Promise<JsonObject>;
  verifyReceipt(electionId: string, receiptHash: string): Promise<JsonObject>;
  metrics(options?: { prometheus?: false }): Promise<JsonObject>;
  metrics(options: { prometheus: true }): Promise<string>;
  auditLogPage(options?: { after?: number; limit?: number }): Promise<AuditLogPage>;
  iterAuditLog(options?: { pageSize?: number }): AsyncGenerator<AuditLogEntry>;
  auditCheckpoints(options?: { interval?: number; limit?: number }): Promise<JsonObject>;
  verifyAuditChain(options?: { fromLogId?: number; prevHash?: string }): Promise<JsonObject>;
  verifyAuditChainLocally(): Promise<LocalAuditVerifyResult>;
}

export declare function verifyAuditEntriesLocally(
  entries: AsyncIterable<AuditLogEntry> | Iterable<AuditLogEntry>,
): Promise<LocalAuditVerifyResult>;

export declare function canonicalJson(value: unknown): string;
