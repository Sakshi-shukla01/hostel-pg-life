export type AiSource = "gemini" | "offline";

export interface User {
  id: string;
  name: string;
  email: string;
  role: "student" | "warden" | "admin";
  hostel: string;
  verified: boolean;
  email_verified?: boolean;
  auth_provider?: "password" | "google";
  picture?: string | null;
}

export interface Answers {
  sleep_time: string;
  wake_time: string;
  study_style: "silent" | "music" | "library";
  cleanliness: number;
  food: "veg" | "nonveg" | "eggetarian" | "flexible";
  smoking: boolean;
  drinking: boolean;
  guests: number;
  noise: number;
  ac: "ac" | "fan" | "either";
  personality: "introvert" | "ambivert" | "extrovert";
}

export interface Profile {
  city: string;
  area: string;
  gender: "male" | "female" | "other";
  gender_pref: "same" | "any";
  budget_min: number;
  budget_max: number;
  move_in: string | null;
  room_type: "2-sharing" | "3-sharing" | "flat";
  college_or_office: string;
  bio: string;
  interests: string[];
  answers: Answers;
  dealbreakers: string[];
}

export interface Match {
  user_id: string;
  name: string;
  verified: boolean;
  college_or_office: string;
  area: string;
  budget_min: number;
  budget_max: number;
  bio: string;
  answers: Answers;
  score: number;
  habits_score: number;
  personality_score: number;
  embedding_source: "gemini" | "local";
  weights_source: "default" | "learned";
  reasons: string[];
  conflicts: string[];
  request_status: string | null;
}

export interface MatchRequest {
  id: string;
  direction: "incoming" | "outgoing";
  status: "pending" | "accepted" | "rejected";
  message: string;
  other_user: { id: string; name: string; verified: boolean; email?: string };
  created_at: string;
}

export interface Message {
  id: string;
  sender: string;
  text: string;
  created_at: string;
  flagged: boolean;
  warning: string;
}

export interface Expense {
  id: string;
  title: string;
  amount: number;
  category: string;
  paid_by: string;
  shares: Record<string, number>;
  created_at: string;
}

export interface Chore {
  id: string;
  task: string;
  assigned_to: string;
  done_count: number;
  last_done: string | null;
}

export interface Room {
  id: string;
  name: string;
  members: { id: string; name: string; email: string }[];
  balances: Record<string, number>;
  payments: { from_user: string; to_user: string; amount: number }[];
  expenses: Expense[];
  chores: Chore[];
  agreement: { text: string; source: AiSource; agreed_by: string[] } | null;
  rated: string[];
}

export interface Complaint {
  id: string;
  title: string;
  description: string;
  room_no: string;
  raiser_name: string;
  photo_url: string | null;
  category: string;
  priority: "low" | "medium" | "high";
  ai_summary: string;
  ai_source: AiSource;
  status: "open" | "in_progress" | "resolved";
  notes: { by: string; text: string; at: string }[];
  rating: number | null;
  escalated: boolean;
  created_at: string;
}

export interface Listing {
  id: string;
  title: string;
  description: string;
  price: number;
  category: string;
  condition: string;
  location: string;
  photo_url: string | null;
  seller: string;
  seller_name: string;
  seller_verified: boolean;
  status: string;
  flag_reason: string;
}
