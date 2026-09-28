export interface Profile {
  id: string;
  email: string;
  name: string;
  phone: string | null;
  district: string | null;
  state: string | null;
  village: string | null;
  latitude: number | null;
  longitude: number | null;
  location_source: string | null;
  farm_size_acres: number;
  soil_type: string;
  water_availability: string;
  language: string;
  avatar_url: string | null;
  role: string;
  onboarding_completed: boolean;
  created_at: string;
}

export interface Farm {
  id: string;
  user_id: string;
  name: string;
  district: string | null;
  state: string | null;
  village: string | null;
  area_acres: number;
  soil_type: string;
  water_source: string;
  current_crop: string | null;
  current_season: string | null;
  planting_date: string | null;
  latitude: number | null;
  longitude: number | null;
  created_at: string;
}

export interface CropRecommendationItem {
  crop_name: string;
  investment_inr: number;
  expected_revenue_inr: number;
  expected_profit_inr: number;
  risk_score: number;
  confidence_score: number;
  yield_quintals_per_acre: number | null;
  duration_days: number | null;
  why_recommended: string;
  risks: string[];
}

export interface Recommendation {
  id: string;
  location: string;
  season: string;
  farm_size_acres: number;
  crops: CropRecommendationItem[];
  model: string | null;
  created_at: string;
}

export interface DiseaseReport {
  id: string;
  crop: string;
  image_url: string | null;
  disease_name: string;
  is_healthy: boolean;
  confidence: number;
  severity: string;
  severity_score: number;
  symptoms: string | null;
  cause: string | null;
  treatment: string | null;
  prevention: string | null;
  spread_risk: string | null;
  alternatives?: string[] | null;
  followup_status?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface ProfitScenario {
  yield_quintals: number;
  price_per_quintal: number;
  revenue_inr: number;
  profit_inr: number;
  roi_percent: number;
}

export interface ProfitPrediction {
  id: string;
  crop: string;
  farm_size_acres: number;
  total_cost: number;
  expected_yield_quintals: number;
  expected_price_per_quintal: number;
  expected_revenue: number;
  expected_profit: number;
  roi: number;
  risk_score: number;
  confidence_score: number;
  scenarios: {
    best?: ProfitScenario;
    average?: ProfitScenario;
    worst?: ProfitScenario;
  };
  created_at: string;
}

export interface MarketPricePoint {
  date: string;
  price: number;
}

export interface MarketPrediction {
  id: string;
  crop: string;
  market: string | null;
  current_price: number;
  price_unit: string;
  trend_weekly: number;
  trend_monthly: number;
  trend_quarterly: number;
  demand_forecast: string | null;
  supply_forecast: string | null;
  price_forecast_7d: number;
  price_forecast_14d: number;
  price_forecast_30d: number;
  recommendation: "sell_now" | "wait_1_week" | "wait_2_weeks" | "hold";
  confidence: number;
  reasoning: string | null;
  price_history: MarketPricePoint[];
  data_source?: string | null;
  source_meta?: { scope?: string; commodity?: string } | null;
  created_at: string;
}

export interface WeatherDay {
  date: string;
  temp_c: number | null;
  temp_max_c?: number | null;
  temp_min_c?: number | null;
  feels_like_c: number | null;
  humidity: number | null;
  wind_kph: number | null;
  precip_mm: number | null;
  precip_probability: number | null;
  condition: string;
}

export interface WeatherIntelligence {
  location: string;
  days: WeatherDay[];
  ai_recommendation: string | null;
  action: string | null;
  alerts: string[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  agent: string | null;
  created_at: string;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Notification {
  id: string;
  type: "weather" | "disease" | "market" | "profit" | "system" | "action";
  channel: string;
  title: string;
  body: string;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

export interface Activity {
  id: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AnalyticsKpis {
  expected_revenue: number;
  expected_profit: number;
  disease_frequency: number;
  yield_growth: number;
  profit_growth: number;
  weather_risk: number;
  recommendation_accuracy: number;
  profit_prediction_accuracy: number;
}

export interface TodayPlanPriority {
  rank: number;
  icon: string;
  level: "low" | "medium" | "high";
  title: string;
  detail: string;
  basis: string;
}

export interface TodayPlan {
  generated_for: string;
  farm: {
    name: string | null;
    size_acres: number;
    village: string | null;
    district: string | null;
    state: string | null;
    crop: string | null;
    planting_date: string | null;
    crop_age_days: number | null;
    crop_stage: string | null;
    soil_type: string;
    water_source: string;
  };
  weather: {
    summary: string;
    rain_probability: number | null;
    rain_mm: number | null;
    source: string;
  } | null;
  crop_health: {
    has_open_issue: boolean;
    crop?: string;
    possible_issue?: string;
    confidence?: number;
    severity?: string;
    followup_status?: string;
    days_ago?: number;
  };
  market: {
    crop: string;
    price: number;
    unit: string;
    trend_weekly_pct: number;
    source: string;
    is_live: boolean;
    as_of: string;
  } | null;
  economics: {
    estimated_cost: number;
    estimated_revenue: number;
    estimated_profit: number;
    crop: string | null;
    recorded_expenses_total: number;
    last_harvest: { crop: string; yield_quintals: number; price_per_quintal: number; revenue_inr: number } | null;
  };
  priorities: TodayPlanPriority[];
  disclaimer: string;
}

export interface ExpenseItem {
  id: string;
  category: string;
  amount_inr: number;
  description: string | null;
  spent_on: string;
}

export interface HarvestItem {
  id: string;
  crop: string;
  harvest_date: string | null;
  actual_yield_quintals: number | null;
  selling_price_per_quintal: number | null;
  market_name: string | null;
  revenue_inr: number | null;
}

export interface EstimatedVsActual {
  estimated: { crop: string | null; yield_quintals: number | null; price_per_quintal: number | null; revenue: number | null; cost: number | null; profit: number | null };
  actual: { crop: string | null; yield_quintals: number | null; price_per_quintal: number | null; revenue: number | null; cost: number | null; profit: number | null };
  difference: Record<string, number | null>;
  has_comparison: boolean;
}

export interface TimelineEvent {
  date: string;
  type: string;
  title: string;
  detail: string;
}

export interface DashboardData {
  location?: {
    label: string;
    precision: string;
    latitude: number;
    longitude: number;
  };
  farm?: {
    farm_size_acres: number;
    village: string | null;
    district: string | null;
    state: string | null;
    soil_type: string;
    water_source: string;
    current_crop: string;
    current_season: string;
  };
  crop_health?: {
    recent_scans: {
      id: string;
      crop: string;
      disease_name: string;
      is_healthy: boolean;
      severity: string;
      followup_status: string | null;
      image_url: string | null;
      created_at: string | null;
    }[];
    open_issues: number;
  };
  widgets: {
    current_crop: string;
    current_season: string;
    expected_revenue: number;
    expected_profit: number;
    risk_score: number;
    disease_alerts: number;
    weather_alerts: string[];
    weather_action?: string | null;
    ai_recommendation?: string | null;
    weather_stale?: boolean;
    market_recommendations: {
      crop: string;
      price: number;
      recommendation: string;
      trend_weekly: number;
    }[];
  };
  charts: {
    revenue_projection: { label: string; value: number }[];
    profit_projection: { label: string; value: number }[];
    yield_estimation: { label: string; value: number }[];
    demand_forecast: { label: string; value: number }[];
    weather_forecast: WeatherDay[];
  };
}
