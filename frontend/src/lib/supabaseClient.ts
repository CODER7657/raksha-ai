import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    "Missing VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY — copy .env.example to .env.local and fill them in."
  );
}

// Safe to expose: the anon key only grants what RLS policies allow.
// Never put the service role key in frontend code.
export const supabase = createClient(supabaseUrl, supabaseAnonKey);
