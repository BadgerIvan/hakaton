export interface User {
  id: string;
  name: string;
  email: string;
}

export interface AuthSession {
  user: User;
  csrf_token: string;
  expires_at: string;
}

export interface Source {
  doc_id: string;
  source: string;
  page?: number | null;
  score?: number;
  url?: string;
}

export type MessageStatus = "complete" | "streaming" | "error" | "cancelled";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  status: MessageStatus;
  error?: string | null;
  request_id?: string;
}

export interface Conversation {
  id: string;
  title: string;
  updatedAt: number;
  messages: Message[];
}
