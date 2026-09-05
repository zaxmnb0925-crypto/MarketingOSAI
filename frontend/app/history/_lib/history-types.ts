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
  generated_content: string | null;
  created_at: string;
  updated_at: string;
};

export {
  type Workspace,
  type MeResponse,
  type Brand,
  type ContentItem,
};
