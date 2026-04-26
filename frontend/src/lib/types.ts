export interface CostMetrics {
    total_cost: number;
    cost_per_message: number;
    total_tokens: number;
    average_tokens_per_message: number;
    input_tokens: number;
    output_tokens: number;
    primary_model: string;
    cache_creation_tokens: number;
    cache_read_tokens: number;
}

export interface QualityMetrics {
    overall_score: number | null;
    grade: string | null;
    query_specificity_score: number | null;
    context_utilization_score: number | null;
    prompt_efficiency_score: number | null;
    vague_queries_count: number | null;
    specific_queries_count: number | null;
    redundant_requests_count: number | null;
    cache_read_millions: number | null;
    cache_read_severity: string | null;
    cache_score: number | null;
    length_severity: string | null;
    length_score: number | null;
    message_count: number | null;
}

export interface CompactionEvent {
    message_index: number;
    timestamp: string;
    cache_read_before: number;
    cache_read_after: number;
    token_drop: number;
}

export interface TokenProgressionEntry {
    message_index: number;
    timestamp: string;
    cache_read_tokens: number;
    cache_creation_tokens: number;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    is_compaction_event: boolean;
    token_drop: number;
}

export interface CompactionData {
    compaction_count: number;
    should_have_compacted: boolean;
    messages_per_compaction: number;
    compaction_events: CompactionEvent[];
    token_progression: TokenProgressionEntry[];
}

export interface ConversationMessage {
    type: string;
    content: string;
    timestamp: string | null;
    message_label: string;
    is_meta: boolean;
}

export interface Conversation {
    session_id: string;
    title: string;
    start_time: string | null;
    duration_minutes: number | null;
    user_prompts: string[];
    cost_metrics: CostMetrics;
    quality_metrics: QualityMetrics | null;
    issues: string[];
    compaction_data: CompactionData | null;
    messages?: ConversationMessage[];
}

export interface ProjectMetrics {
    total_conversations: number;
    total_cost: number;
    total_tokens: number;
    total_input_tokens: number;
    total_output_tokens: number;
    average_score: number;
    total_issues: number;
    date_range_start: string | null;
    date_range_end: string | null;
}

export interface Project {
    id: number;
    name: string;
    clean_name: string;
    path: string | null;
    conversations: Conversation[];
    metrics: ProjectMetrics;
}

export interface OverallMetrics {
    total_projects: number;
    total_conversations: number;
    total_cost: number;
    average_score: number;
    total_tokens: number;
}

export interface AnalysisData {
    projects: Project[];
    overall_metrics: OverallMetrics;
    analysis_timestamp: string;
    generator_info: {
        tool: string;
        version: string;
        export_timestamp: string;
    };
}

export interface SessionDetail {
    session_id: string;
    title: string;
    project_id: number;
    project_name: string;
    start_time: string | null;
    duration_minutes: number | null;
    cost_metrics: CostMetrics;
    quality_metrics: QualityMetrics | null;
    compaction_data: CompactionData | null;
    messages: ConversationMessage[];
}

export type SortKey =
    | "cost"
    | "conversations"
    | "name"
    | "date"
    | "compactions"
    | "duration";
export type SortDirection = "asc" | "desc";
