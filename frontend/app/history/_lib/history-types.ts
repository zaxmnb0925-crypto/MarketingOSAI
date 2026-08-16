type Workspace = {
  id: string;
  name: string;
  slug: string;
  role: string;
};

type MeResponse = {
  user: {
    id: string;
    email: string;
    full_name: string | null;
    is_active: boolean;
  };

  workspaces: Workspace[];
};

type Brand = {
  id: string;
  workspace_id: string;
  name: string;
  industry: string | null;
};

type ContentItem = {
  id: string;
  workspace_id: string;
  brand_id: string;
  platform: string;
  topic: string;
  objective: string | null;
  status: string;
  prompt: string | null;
  generated_content: string | null;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: string | null;
  error_message: string | null;
  created_at?: string;
};

export {
  type Workspace,
  type MeResponse,
  type Brand,
  type ContentItem,
};
