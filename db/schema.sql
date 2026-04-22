-- Quote table for storing real-time market data
-- Primary key ensures uniqueness per symbol and timestamp
CREATE TABLE IF NOT EXISTS public.quote (
    -- Unique identifier for each quote record
    id UUID NOT NULL PRIMARY KEY,
    -- Stock symbol (e.g., 'AAPL')
    symbol TEXT NOT NULL,
    -- Current trading price 
    current_price DECIMAL(15, 4),
    -- Opening price of the trading day
    open_price DECIMAL(15, 4),
    -- Highest price of the trading day
    high_price DECIMAL(15, 4),
    -- Lowest price of the trading day
    low_price DECIMAL(15, 4),
    -- Previous day's closing price
    previous_close_price DECIMAL(15, 4),
    -- Calculated price change
    price_change DECIMAL(15, 4),
    -- Calculated percentage change
    price_change_percent DECIMAL(15, 4),
    -- Unix timestamp of the quote
    created_at TIMESTAMPTZ NOT NULL,
    -- Primary key on symbol and timestamp
    CONSTRAINT symbol_timestamp UNIQUE (symbol, created_at)
);

-- Anomaly table for storing market anomalies
-- Foreign key points to the quote that triggered the anomaly
CREATE TABLE IF NOT EXISTS public.anomaly (
    -- Unique identifier for each anomaly record
    id UUID NOT NULL PRIMARY KEY,
    -- Reference to the quote
    quote_id UUID NOT NULL REFERENCES public.quote (id),
    -- Stock symbol (e.g., 'AAPL')
    symbol TEXT NOT NULL,
    -- The anomaly price
    price DECIMAL(15, 4),
    -- Anomaly z-score
    price_z_score DECIMAL(15, 2),
    -- Timestamp when the anomaly was detected
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Explanation table for storing anomaly reason and details
-- Foreign key points to the anomaly
CREATE TABLE IF NOT EXISTS public.anomaly_explanation (
    -- Unique identifier for each explanation record
    id UUID NOT NULL PRIMARY KEY,
    -- Reference to the anomaly
    anomaly_id UUID NOT NULL REFERENCES public.anomaly (id),
    -- Stock symbol (e.g., 'AAPL')
    symbol TEXT NOT NULL,
    -- The AI-generated explanation text
    explanation TEXT,
    -- The explanation creation time
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anomaly_quote_id ON public.anomaly (quote_id);

CREATE INDEX IF NOT EXISTS idx_anomaly_explanation_anomaly_id ON public.anomaly_explanation (anomaly_id);