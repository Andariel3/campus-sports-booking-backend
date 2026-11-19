-- ============================================================
-- DATE DE TEST (SEED) - Campus Sports Booking
-- ============================================================

-- 1. Utilizatori (parola pentru toți este "test123" - hash bcrypt generic)
INSERT INTO users (email, first_name, last_name, password_hash, role) VALUES
('admin@test.com', 'Admin', 'Test', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', 'Administrator'),
('profesor@test.com', 'Ion', 'Popescu', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', 'Professor'),
('student1@test.com', 'Andrei', 'Ionescu', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', 'Student'),
('student2@test.com', 'Maria', 'Popa', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', 'Student');

-- 2. Tipuri de sport
INSERT INTO sport_types (label) VALUES
('Fotbal'),
('Baschet'),
('Înot'),
('Tenis');

-- 3. Resurse (Terenuri / Bazine)
INSERT INTO resources (sport_type_id, name, description, price_per_hour, is_active) VALUES
(1, 'Teren Fotbal Central', 'Teren de fotbal cu gazon sintetic', 100.00, TRUE),
(2, 'Teren Baschet 1', 'Teren de baschet în aer liber', 50.00, TRUE),
(3, 'Bazin Olimpic', 'Bazin de înot semi-olimpic', 80.00, TRUE),
(4, 'Teren Tenis 1', 'Teren de tenis cu zgură', 60.00, TRUE);

-- 4. Program de disponibilitate (Luni-Vineri 08:00 - 22:00, Sambata 09:00-18:00)
-- day_of_week: 0=Duminica, 1=Luni, ..., 6=Sambata
INSERT INTO resource_schedules (resource_id, day_of_week, open_time, close_time) VALUES
-- Teren Fotbal
(1, 1, '08:00', '22:00'), (1, 2, '08:00', '22:00'), (1, 3, '08:00', '22:00'), (1, 4, '08:00', '22:00'), (1, 5, '08:00', '22:00'), (1, 6, '09:00', '18:00'),
-- Teren Baschet
(2, 1, '08:00', '22:00'), (2, 2, '08:00', '22:00'), (2, 3, '08:00', '22:00'), (2, 4, '08:00', '22:00'), (2, 5, '08:00', '22:00'),
-- Bazin
(3, 1, '07:00', '21:00'), (3, 2, '07:00', '21:00'), (3, 3, '07:00', '21:00'), (3, 4, '07:00', '21:00'), (3, 5, '07:00', '21:00');

-- 5. Blocări Mentenanță (Exemplu: Terenul de fotbal e în mentenanță mâine)
INSERT INTO maintenance_blocks (resource_id, admin_id, start_time, end_time, reason) VALUES
(1, 1, CURRENT_TIMESTAMP + INTERVAL '1 day', CURRENT_TIMESTAMP + INTERVAL '1 day 4 hours', 'Întreținere gazon');

-- 6. Rezervări
-- Nota: Am folosit CURRENT_DATE + INTERVAL pentru a genera date in viitor, ca sa nu pice constrangerile de timp
INSERT INTO bookings (user_id, resource_id, start_time, end_time, status, is_paid, amount, is_open, max_participants) VALUES
-- Studentul 1 face o rezervare simpla la fotbal
(3, 1, CURRENT_DATE + INTERVAL '2 days 10:00', CURRENT_DATE + INTERVAL '2 days 12:00', 'Confirmed', TRUE, 200.00, FALSE, NULL),
-- Studentul 2 face o rezervare deschisa (open) la baschet, cu max 10 participanti
(4, 2, CURRENT_DATE + INTERVAL '3 days 14:00', CURRENT_DATE + INTERVAL '3 days 16:00', 'Confirmed', FALSE, 100.00, TRUE, 10),
-- Profesorul face o rezervare la bazin
(2, 3, CURRENT_DATE + INTERVAL '4 days 08:00', CURRENT_DATE + INTERVAL '4 days 09:00', 'Confirmed', TRUE, 80.00, FALSE, NULL),
-- O rezervare anulata
(3, 4, CURRENT_DATE + INTERVAL '5 days 10:00', CURRENT_DATE + INTERVAL '5 days 11:00', 'Cancelled', FALSE, 60.00, FALSE, NULL);

-- 7. Participanți la Rezervarea Deschisă (Studentul 1 s-a înscris la baschetul Studentului 2)
INSERT INTO booking_participants (booking_id, user_id) VALUES
(2, 3); -- ID-ul 3 este student1@test.com, ID-ul 2 este rezervarea de la baschet

-- 8. Lista de așteptare
-- Studentul 1 vrea la bazin, dar e ocupat (sau vrea in alt interval)
INSERT INTO waitlist_entries (user_id, resource_id, start_time, end_time, status) VALUES
(3, 3, CURRENT_DATE + INTERVAL '4 days 10:00', CURRENT_DATE + INTERVAL '4 days 11:00', 'Waiting');

-- 9. Notificări (Exemplu)
INSERT INTO notifications (user_id, booking_id, type, is_sent) VALUES
(3, 1, 'BookingConfirmation', TRUE),
(4, 2, 'BookingConfirmation', FALSE);