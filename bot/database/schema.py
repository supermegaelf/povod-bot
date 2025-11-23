CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    role VARCHAR(32) NOT NULL DEFAULT 'user',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);
"""

CREATE_EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    time TIME,
    end_date DATE,
    end_time TIME,
    place VARCHAR(255),
    description TEXT,
    cost DECIMAL(10, 2) DEFAULT 0,
    image_file_id VARCHAR(255),
    max_participants INTEGER,
    reminder_3days BOOLEAN NOT NULL DEFAULT FALSE,
    reminder_1day BOOLEAN NOT NULL DEFAULT FALSE,
    reminder_3days_sent_at TIMESTAMP WITHOUT TIME ZONE,
    reminder_1day_sent_at TIMESTAMP WITHOUT TIME ZONE,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);
"""

CREATE_EVENT_IMAGES = """
CREATE TABLE IF NOT EXISTS event_images (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    file_id VARCHAR(255) NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);
"""

ALTER_EVENTS_PLACE_NULL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'events' 
        AND column_name = 'place' 
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE events ALTER COLUMN place DROP NOT NULL;
    END IF;
END $$;
"""

ALTER_EVENTS_TIME_NULL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'events' 
        AND column_name = 'time' 
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE events ALTER COLUMN time DROP NOT NULL;
    END IF;
END $$;
"""

ALTER_EVENTS_ADD_END_DATE = """
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS end_date DATE;
"""

ALTER_EVENTS_ADD_END_TIME = """
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS end_time TIME;
"""

ALTER_EVENTS_ADD_REMINDER_SENT_3 = """
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS reminder_3days_sent_at TIMESTAMP WITHOUT TIME ZONE;
"""

ALTER_EVENTS_ADD_REMINDER_SENT_1 = """
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS reminder_1day_sent_at TIMESTAMP WITHOUT TIME ZONE;
"""

CREATE_REGISTRATIONS = """
CREATE TABLE IF NOT EXISTS registrations (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'going',
    registered_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(event_id, user_id)
);
"""

CREATE_PAYMENTS = """
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    payment_id VARCHAR(255) UNIQUE NOT NULL,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    paid_at TIMESTAMP WITHOUT TIME ZONE,
    confirmation_url TEXT,
    payment_message_id INTEGER
);
"""

ALTER_PAYMENTS_ADD_MESSAGE_ID = """
ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS payment_message_id INTEGER;
"""

ALTER_PROMOCODES_UNIQUE_CONSTRAINT = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'promocodes_code_key'
    ) THEN
        ALTER TABLE promocodes DROP CONSTRAINT promocodes_code_key;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'promocodes_event_id_code_key'
    ) THEN
        ALTER TABLE promocodes ADD CONSTRAINT promocodes_event_id_code_key UNIQUE (event_id, code);
    END IF;
END $$;
"""

ALTER_USERS_ADD_FIRST_NAME = """
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS first_name VARCHAR(255);
"""

ALTER_USERS_ADD_LAST_NAME = """
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS last_name VARCHAR(255);
"""

CREATE_PROMOCODES = """
CREATE TABLE IF NOT EXISTS promocodes (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    code VARCHAR(64) NOT NULL,
    discount_amount DECIMAL(10, 2) NOT NULL,
    expires_at TIMESTAMP WITHOUT TIME ZONE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    used_by_user_id INTEGER REFERENCES users(id),
    used_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(event_id, code)
);
"""

CREATE_PROMOCODE_USAGES = """
CREATE TABLE IF NOT EXISTS promocode_usages (
    id SERIAL PRIMARY KEY,
    promocode_id INTEGER NOT NULL REFERENCES promocodes(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    used_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(promocode_id, user_id)
);
"""

CREATE_BOT_MESSAGES = """
CREATE TABLE IF NOT EXISTS bot_messages (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chat_id BIGINT NOT NULL,
    message_id INTEGER NOT NULL,
    sent_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(chat_id, message_id)
);
"""

CREATE_INDEX_BOT_MESSAGES_USER = """
CREATE INDEX IF NOT EXISTS idx_bot_messages_user_id ON bot_messages(user_id);
"""

CREATE_INDEX_BOT_MESSAGES_CHAT = """
CREATE INDEX IF NOT EXISTS idx_bot_messages_chat_id ON bot_messages(chat_id);
"""

CREATE_INDEX_BOT_MESSAGES_SENT_AT = """
CREATE INDEX IF NOT EXISTS idx_bot_messages_sent_at ON bot_messages(sent_at);
"""

STATEMENTS = (
    CREATE_USERS,
    CREATE_EVENTS,
    ALTER_EVENTS_PLACE_NULL,
    ALTER_EVENTS_TIME_NULL,
    ALTER_EVENTS_ADD_END_DATE,
    ALTER_EVENTS_ADD_END_TIME,
    ALTER_EVENTS_ADD_REMINDER_SENT_3,
    ALTER_EVENTS_ADD_REMINDER_SENT_1,
    CREATE_EVENT_IMAGES,
    CREATE_REGISTRATIONS,
    CREATE_PAYMENTS,
    ALTER_PAYMENTS_ADD_MESSAGE_ID,
    CREATE_PROMOCODES,
    ALTER_PROMOCODES_UNIQUE_CONSTRAINT,
    CREATE_PROMOCODE_USAGES,
    ALTER_USERS_ADD_FIRST_NAME,
    ALTER_USERS_ADD_LAST_NAME,
    CREATE_BOT_MESSAGES,
    CREATE_INDEX_BOT_MESSAGES_USER,
    CREATE_INDEX_BOT_MESSAGES_CHAT,
    CREATE_INDEX_BOT_MESSAGES_SENT_AT,
)

