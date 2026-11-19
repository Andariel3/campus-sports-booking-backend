-- ============================================================
-- CAMPUS SPORTS BOOKING - Script complet de creare a bazei de date
-- PostgreSQL 16
-- ============================================================

-- 1. Activarea extensiei pentru constrângeri de excludere (prevenirea suprapunerilor)
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 2. Crearea tipurilor ENUM
CREATE TYPE role_enum AS ENUM ('Student', 'Professor', 'Administrator');
CREATE TYPE booking_status_enum AS ENUM ('Confirmed', 'Cancelled', 'NoShow');
CREATE TYPE waitlist_status_enum AS ENUM ('Waiting', 'Notified', 'Expired');
CREATE TYPE notification_type_enum AS ENUM ('BookingConfirmation', 'BookingCancellation', 'WaitlistSlotFree');

-- 3. Tabelul Utilizatori (User)
CREATE TABLE users (
id SERIAL PRIMARY KEY,
email VARCHAR(255) UNIQUE NOT NULL,
first_name VARCHAR(100) NOT NULL,
last_name VARCHAR(100) NOT NULL,
password_hash VARCHAR(255) NOT NULL,
role role_enum NOT NULL DEFAULT 'Student',
blocked_until TIMESTAMP WITH TIME ZONE,
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Tabelul Tipuri de Sport (SportType)
CREATE TABLE sport_types (
id SERIAL PRIMARY KEY,
label VARCHAR(100) UNIQUE NOT NULL
);

-- 5. Tabelul Resurse (Resource)
CREATE TABLE resources (
id SERIAL PRIMARY KEY,
sport_type_id INTEGER REFERENCES sport_types(id) ON DELETE RESTRICT,
name VARCHAR(150) NOT NULL,
description TEXT,
price_per_hour NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
is_active BOOLEAN DEFAULT TRUE
);

-- 6. Tabelul Program de Disponibilitate (ResourceSchedule)
CREATE TABLE resource_schedules (
id SERIAL PRIMARY KEY,
resource_id INTEGER REFERENCES resources(id) ON DELETE CASCADE,
day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
open_time TIME NOT NULL,
close_time TIME NOT NULL,
is_active BOOLEAN DEFAULT TRUE,
CONSTRAINT check_schedule_times CHECK (open_time < close_time),
CONSTRAINT unique_resource_day UNIQUE (resource_id, day_of_week)
);

-- 7. Tabelul Blocări Mentenanță (MaintenanceBlock)
CREATE TABLE maintenance_blocks (
id SERIAL PRIMARY KEY,
resource_id INTEGER REFERENCES resources(id) ON DELETE CASCADE,
admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
start_time TIMESTAMP WITH TIME ZONE NOT NULL,
end_time TIMESTAMP WITH TIME ZONE NOT NULL,
reason TEXT,
CONSTRAINT check_maintenance_dates CHECK (start_time < end_time)
);

-- 8. Tabelul Rezervări (Booking)
CREATE TABLE bookings (
id SERIAL PRIMARY KEY,
user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
resource_id INTEGER REFERENCES resources(id) ON DELETE CASCADE,
start_time TIMESTAMP WITH TIME ZONE NOT NULL,
end_time TIMESTAMP WITH TIME ZONE NOT NULL,
status booking_status_enum NOT NULL DEFAULT 'Confirmed',
is_paid BOOLEAN DEFAULT FALSE,
paid_at TIMESTAMP WITH TIME ZONE,
amount NUMERIC(10, 2) NOT NULL,
is_open BOOLEAN DEFAULT FALSE,
max_participants INTEGER,
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
cancelled_at TIMESTAMP WITH TIME ZONE,
cancelled_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,



CONSTRAINT check_booking_dates CHECK (start_time < end_time),
-- CONSTRÂNGEREA CRITICĂ: Prevenirea suprapunerilor
CONSTRAINT prevent_overlapping_bookings EXCLUDE USING gist (
    resource_id WITH =,
    tstzrange(start_time, end_time) WITH &&
) WHERE (status != 'Cancelled')
);

-- 9. Tabelul Participanți la Rezervări Deschise (BookingParticipant)
CREATE TABLE booking_participants (
booking_id INTEGER REFERENCES bookings(id) ON DELETE CASCADE,
user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY (booking_id, user_id)
);

-- 10. Tabelul Listă de Așteptare (WaitlistEntry)
CREATE TABLE waitlist_entries (
id SERIAL PRIMARY KEY,
user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
resource_id INTEGER REFERENCES resources(id) ON DELETE CASCADE,
start_time TIMESTAMP WITH TIME ZONE NOT NULL,
end_time TIMESTAMP WITH TIME ZONE NOT NULL,
status waitlist_status_enum NOT NULL DEFAULT 'Waiting',
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 11. Tabelul Notificări (Notification)
CREATE TABLE notifications (
id SERIAL PRIMARY KEY,
user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
booking_id INTEGER REFERENCES bookings(id) ON DELETE SET NULL,
type notification_type_enum NOT NULL,
sent_at TIMESTAMP WITH TIME ZONE,
is_sent BOOLEAN DEFAULT FALSE
);

-- 12. Indexuri pentru optimizarea interogărilor frecvente
CREATE INDEX idx_bookings_user_date ON bookings(user_id, start_time);
CREATE INDEX idx_bookings_resource_date ON bookings(resource_id, start_time);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_waitlist_resource_time ON waitlist_entries(resource_id, start_time);
CREATE INDEX idx_notifications_user ON notifications(user_id);