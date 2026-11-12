-- ========================================================================
-- Scuola Dei Bambini De Sta. Terisita International Montessori School Inc.
-- Campus E-Wallet & Canteen POS System Database Dump
-- Ready for MySQL Workbench / MySQL Server 8.0+
-- ========================================================================

CREATE DATABASE IF NOT EXISTS school_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE school_system;

SET FOREIGN_KEY_CHECKS = 0;

-- Table structure for `students`
DROP TABLE IF EXISTS `students`;
CREATE TABLE IF NOT EXISTS students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    school_id VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    parent_email VARCHAR(120),
    contact_number VARCHAR(20),
    grade_level VARCHAR(20),
    strand VARCHAR(50),
    guardian_name VARCHAR(100),
    pin VARCHAR(255) DEFAULT '1234',
    password VARCHAR(255) NOT NULL,
    security_q1 VARCHAR(255),
    security_a1 VARCHAR(255),
    security_q2 VARCHAR(255),
    security_a2 VARCHAR(255),
    security_q3 VARCHAR(255),
    security_a3 VARCHAR(255),
    balance DECIMAL(10, 2) DEFAULT 0.00,
    qr_code VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active',
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dumping data for `students` (7 rows)
INSERT INTO `students` (`student_id`, `school_id`, `full_name`, `email`, `parent_email`, `contact_number`, `strand`, `guardian_name`, `grade_level`, `password`, `pin`, `security_q1`, `security_a1`, `security_q2`, `security_a2`, `security_q3`, `security_a3`, `balance`, `qr_code`, `status`, `last_active`, `created_at`) VALUES
  (1, '2026001', 'Juan Dela Cruz', 'juandelacruz@gmail.com', 'parentjuan@gmail.com', '09171234567', 'STEM', 'Maria Dela Cruz', '12', 'pbkdf2:sha256:1000000$kpAe3pauvNsGmLDd$f948a51ac6a133f10e6e1301c8fc3bc9375e5aa01abe82a845011a576feecce0', '1234', 'Pet?', 'Bantay', 'City?', 'Manila', 'Food?', 'Adobo', 35, 'static\\qrcodes\\2026001.png', 'active', '2026-10-16 08:13:47', '2026-10-16 08:13:47'),
  (2, '7659876', 'Toshi', 'sanielken2@gmail.com', 'ashinomoto23@gmail.com', '09276879042', 'STEM', 'Ashi', 'Grade 11', 'pbkdf2:sha256:1000000$Bow3vqwFS4bJvGtB$741b24355168e010a5e3ffc2f7e09f83b73f023f7c52c2921335e6791cece7cc', '4321', 'birth_city', 'Atimonan', 'best_friend', 'Shido', 'favorite_color', 'Red', 950, 'static\\qrcodes\\7659876.png', 'active', '2026-10-16 08:23:58', '2026-10-16 08:23:58'),
  (3, '2311369', 'Jankrishna miranda', 'jankrishnamiranda21@gmail.com', 'Jankrishnamiranda25@gmail.com', '09761666302', 'ABM', 'Josie Miranda', 'Grade 11', 'pbkdf2:sha256:1000000$lU8Qffr38KD12iop$a8470b2f5ef35a3ddb3ecc900068ff629f3da5ece33da9780ddfb16dafb55dc7', '8214', 'mother_maiden', 'Josie', 'first_school', 'Ambray', 'favorite_color', 'Red', 37505, 'static\\qrcodes\\2311369.png', 'active', '2026-10-18 05:57:15', '2026-10-18 05:57:15'),
  (4, '2311375', 'Eldrick Paran Bacod', 'eldrickb00@gmail.com', 'bacodjasmin@gmail.com', '09708454679', 'TVL', 'Jasmin Paran Bacod', 'Grade 12', 'pbkdf2:sha256:1000000$XF7ftOkr1nllKbRo$d02343b52ffeb4d88dcdd1df7f13840cbac364ccc8cf694d610f4b35aafb9b20', '1114', 'first_pet', 'ewings', 'best_friend', 'chloe', 'favorite_color', 'black', 5200, 'static\\qrcodes\\2311375.png', 'active', '2026-10-18 05:59:49', '2026-10-18 05:59:49'),
  (5, '0987654', 'Mark Chester Yanga', 'chester292005@gmail.com', 'parents21@gmail.com', '09134567890', 'TVL', 'Mina yanga', 'Grade 12', 'pbkdf2:sha256:1000000$R7x6afNybhC2yxaw$aca15659aec498c73717ee6e4d398041a6c5cbcb94f6dcb262edf562f0b4bbe5', '1111', 'mother_maiden', 'dunno', 'first_school', 'dimagiba', 'favorite_book', 'A farewell to arms', 500, 'static\\qrcodes\\0987654.png', 'active', '2026-10-18 06:01:04', '2026-10-18 06:01:04'),
  (6, '1235678', 'Kalbaryo de kalibre', 'yckotoshihernandez8@gmail.com', 'kalbo@gmail.com', '09936748658', 'HUMMS', 'Kambing', 'Grade 11', 'pbkdf2:sha256:1000000$4pnsP7ECUOX5ddeU$834c156861ab58baca707518e48b543df683767ee42e0b2da13db75c16beec85', '1111', 'mother_maiden', 'Asbog', 'first_school', 'Scoula', 'favorite_book', 'Booking', 500000, 'static\\qrcodes\\1235678.png', 'active', '2026-10-18 06:01:23', '2026-10-18 06:01:23'),
  (7, '1234567', 'Karl', 'karlmartinez475@gmail.com', 'barabasjudas08@gmail.com', '09876543210', 'HUMMS', 'Carlo', 'Grade 12', 'pbkdf2:sha256:1000000$6oCwZGX317Nn1mdz$60db119890ebdc2fa378ff146aaa7c0c2442d9d1546438f4be96d344e5f29189', '1234', 'first_pet', 'Mingming', 'best_friend', 'Charlie', 'favorite_color', 'Blue', 99410, 'static\\qrcodes\\1234567.png', 'active', '2026-10-18 06:02:05', '2026-10-18 06:02:05');

-- Table structure for `admins`
DROP TABLE IF EXISTS `admins`;
CREATE TABLE IF NOT EXISTS admins (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    contact_number VARCHAR(20),
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    security_q1 VARCHAR(255),
    security_a1 VARCHAR(255),
    security_q2 VARCHAR(255),
    security_a2 VARCHAR(255),
    security_q3 VARCHAR(255),
    security_a3 VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dumping data for `admins` (2 rows)
INSERT INTO `admins` (`admin_id`, `full_name`, `contact_number`, `email`, `password`, `security_q1`, `security_a1`, `security_q2`, `security_a2`, `security_q3`, `security_a3`, `created_at`) VALUES
  (1, 'Admin User', '09181234567', 'adminuser@gmail.com', 'pbkdf2:sha256:1000000$0fhqmbEYoIRYp1nT$0b02bf6884e47cf1813cebcc08be353e907309c1b321c63dd2f0785b64be7708', 'Q1', 'Answer1', 'Q2', 'Answer2', 'Q3', 'Answer3', '2026-10-16 08:14:13'),
  (2, 'Jodelyn Marvs', '09667890543', 'jodelynmarvilla@gmail.com', 'pbkdf2:sha256:1000000$DHIHTf9ClFKkQn9Y$e0eeb7e07d343441305532eee5ac4e6c871f39d26859a488f533106bb2a37d34', 'nickname', 'JJ', 'dream_job', 'Nurse', 'favorite_color', 'Blue', '2026-10-16 10:41:26');

-- Table structure for `staff`
DROP TABLE IF EXISTS `staff`;
CREATE TABLE IF NOT EXISTS staff (
    staff_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    contact_number VARCHAR(20),
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    staff_qr VARCHAR(255),
    security_q1 VARCHAR(255),
    security_a1 VARCHAR(255),
    security_q2 VARCHAR(255),
    security_a2 VARCHAR(255),
    security_q3 VARCHAR(255),
    security_a3 VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dumping data for `staff` (2 rows)
INSERT INTO `staff` (`staff_id`, `full_name`, `contact_number`, `email`, `password`, `staff_qr`, `security_q1`, `security_a1`, `security_q2`, `security_a2`, `security_q3`, `security_a3`, `created_at`) VALUES
  (1, 'Staff User', '09191234567', 'staffuser@gmail.com', 'pbkdf2:sha256:1000000$FEnXN0WePKrZXmN6$cba91fd96723aae6ddae7ca0e72eda35dde9ca1250fd74eadb2617a8981cf85d', NULL, 'Q1', 'Answer1', 'Q2', 'Answer2', 'Q3', 'Answer3', '2026-10-16 08:14:30'),
  (2, 'Ace Pinata', '09653345678', 'morenongkups@gmail.com', 'pbkdf2:sha256:1000000$xOrW3OYqajyMP3S4$08275484c7add91ddee7e4204ca94360d52cd544c0c88fc9bc1fba7c288a3600', 'STAFF-2', 'birth_city', 'Atimonan', 'favorite_movie', 'Life', 'hobby', 'Gaming', '2026-10-16 10:09:06');

-- Table structure for `otps`
DROP TABLE IF EXISTS `otps`;
CREATE TABLE IF NOT EXISTS otps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(120) NOT NULL,
    otp_code VARCHAR(20) NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dumping data for `otps` (86 rows)
INSERT INTO `otps` (`id`, `email`, `otp_code`, `expires_at`, `created_at`) VALUES
  (1, 'juandelacruz@gmail.com', '280529', '2026-10-16 16:23:39', '2026-10-16 08:13:43'),
  (2, 'juandelacruz@gmail.com', '142424', '2026-10-16 16:23:56', '2026-10-16 08:14:00'),
  (3, 'adminuser@gmail.com', '654091', '2026-10-16 16:24:17', '2026-10-16 08:14:21'),
  (4, 'staffuser@gmail.com', '782103', '2026-10-16 16:24:35', '2026-10-16 08:14:39'),
  (5, 'sanielken2@gmail.com', '989549', '2026-10-16 16:33:30', '2026-10-16 08:23:34'),
  (6, 'sanielken2@gmail.com', '546613', '2026-10-16 16:34:31', '2026-10-16 08:24:35'),
  (7, 'sanielken2@gmail.com', '930673', '2026-10-16 16:34:33', '2026-10-16 08:24:37'),
  (8, 'sanielken2@gmail.com', '803796', '2026-10-16 16:45:16', '2026-10-16 08:35:20'),
  (9, 'sanielken2@gmail.com', '701247', '2026-10-16 16:55:39', '2026-10-16 08:45:43'),
  (10, 'sanielken2@gmail.com', '326413', '2026-10-16 17:37:37', '2026-10-16 09:27:41'),
  (11, 'sanielken2@gmail.com', '815886', '2026-10-16 17:38:16', '2026-10-16 09:28:20'),
  (12, 'sanielken2@gmail.com', '465930', '2026-10-16 17:38:36', '2026-10-16 09:28:40'),
  (13, 'sanielken2@gmail.com', '470853', '2026-10-16 17:42:49', '2026-10-16 09:32:53'),
  (14, 'sanielken2@gmail.com', '831114', '2026-10-16 17:49:29', '2026-10-16 09:39:33'),
  (15, 'juandelacruz@gmail.com', '281606', '2026-10-16 18:01:09', '2026-10-16 09:51:13'),
  (16, 'sanielken2@gmail.com', '498384', '2026-10-16 18:07:21', '2026-10-16 09:57:25'),
  (17, 'morenongkups@gmail.com', '225892', '2026-10-16 18:19:25', '2026-10-16 10:09:29'),
  (18, 'sanielken2@gmail.com', '130568', '2026-10-16 18:29:22', '2026-10-16 10:19:26'),
  (19, 'sanielken2@gmail.com', '875348', '2026-10-16 18:30:36', '2026-10-16 10:20:40'),
  (20, 'sanielken2@gmail.com', '238712', '2026-10-16 18:44:20', '2026-10-16 10:34:24'),
  (21, 'jodelynmarvilla@gmail.com', '262583', '2026-10-16 18:51:44', '2026-10-16 10:41:48'),
  (22, 'sanielken2@gmail.com', '458291', '2026-10-16 18:54:02', '2026-10-16 10:44:06'),
  (23, 'sanielken2@gmail.com', '997963', '2026-10-16 19:12:25', '2026-10-16 11:02:29'),
  (24, 'sanielken2@gmail.com', '517078', '2026-10-16 20:00:01', '2026-10-16 11:50:01'),
  (25, 'sanielken2@gmail.com', '648628', '2026-10-16 20:18:27', '2026-10-16 12:08:27'),
  (26, 'sanielken2@gmail.com', '838572', '2026-10-16 20:19:18', '2026-10-16 12:09:18'),
  (27, 'sanielken2@gmail.com', '553535', '2026-10-16 20:27:21', '2026-10-16 12:17:21'),
  (28, 'morenongkups@gmail.com', '552460', '2026-10-17 20:06:25', '2026-10-17 11:56:25'),
  (29, 'sanielken2@gmail.com', '774955', '2026-10-17 20:23:47', '2026-10-17 12:13:47'),
  (30, 'sanielken2@gmail.com', '821588', '2026-10-17 20:29:26', '2026-10-17 12:19:26'),
  (31, 'jodelynmarvilla@gmail.com', '633092', '2026-10-17 20:31:47', '2026-10-17 12:21:47'),
  (32, 'jodelynmarvilla@gmail.com', '722483', '2026-10-17 20:32:31', '2026-10-17 12:22:31'),
  (33, 'sanielken2@gmail.com', '558308', '2026-10-17 20:39:43', '2026-10-17 12:29:43'),
  (34, 'sanielken2@gmail.com', '527702', '2026-10-17 20:45:22', '2026-10-17 12:35:22'),
  (35, 'morenongkups@gmail.com', '557594', '2026-10-17 20:46:49', '2026-10-17 12:36:49'),
  (36, 'morenongkups@gmail.com', '931795', '2026-10-17 20:47:48', '2026-10-17 12:37:48'),
  (37, 'sanielken2@gmail.com', '404114', '2026-10-17 20:48:48', '2026-10-17 12:38:48'),
  (38, 'morenongkups@gmail.com', '401781', '2026-10-17 20:51:40', '2026-10-17 12:41:40'),
  (39, 'morenongkups@gmail.com', '560847', '2026-10-17 20:51:56', '2026-10-17 12:41:56'),
  (40, 'morenongkups@gmail.com', '332345', '2026-10-17 20:52:02', '2026-10-17 12:42:02'),
  (41, 'morenongkups@gmail.com', '621154', '2026-10-17 20:52:24', '2026-10-17 12:42:24'),
  (42, 'morenongkups@gmail.com', '709799', '2026-10-17 20:52:58', '2026-10-17 12:42:58'),
  (43, 'sanielken2@gmail.com', '984526', '2026-10-17 20:53:19', '2026-10-17 12:43:19'),
  (44, 'morenongkups@gmail.com', '606258', '2026-10-17 21:01:52', '2026-10-17 12:51:52'),
  (45, 'sanielken2@gmail.com', '981180', '2026-10-17 21:06:28', '2026-10-17 12:56:28'),
  (46, 'jodelynmarvilla@gmail.com', '506975', '2026-10-17 21:07:46', '2026-10-17 12:57:46'),
  (47, 'sanielken2@gmail.com', '297067', '2026-10-17 21:08:41', '2026-10-17 12:58:41'),
  (48, 'morenongkups@gmail.com', '335792', '2026-10-17 21:19:57', '2026-10-17 13:09:57'),
  (49, 'morenongkups@gmail.com', '917560', '2026-10-17 21:52:52', '2026-10-17 13:42:52'),
  (50, 'morenongkups@gmail.com', '129897', '2026-10-17 22:14:12', '2026-10-17 14:04:12'),
  (51, 'jodelynmarvilla@gmail.com', '122446', '2026-10-17 22:25:12', '2026-10-17 14:15:12'),
  (52, 'sanielken2@gmail.com', '161602', '2026-10-18 13:37:06', '2026-10-18 05:27:06'),
  (53, 'sanielken2@gmail.com', '290286', '2026-10-18 13:50:29', '2026-10-18 05:40:29'),
  (54, 'jodelynmarvilla@gmail.com', '664205', '2026-10-18 13:51:47', '2026-10-18 05:41:47'),
  (55, 'jankrishnamiranda21@gmail.com', '703961', '2026-10-18 14:06:32', '2026-10-18 05:56:32'),
  (56, 'jankrishnamiranda21@gmail.com', '430248', '2026-10-18 14:07:59', '2026-10-18 05:57:59'),
  (57, 'eldrickb00@gmail.com', '178770', '2026-10-18 14:09:00', '2026-10-18 05:59:00'),
  (58, 'chester292005@gmail.com', '880680', '2026-10-18 14:10:36', '2026-10-18 06:00:36'),
  (59, 'chester292005@gmail.com', '737872', '2026-10-18 14:10:37', '2026-10-18 06:00:37'),
  (60, 'eldrickb00@gmail.com', '194552', '2026-10-18 14:10:40', '2026-10-18 06:00:40'),
  (61, 'yckotoshihernandez8@gmail.com', '433122', '2026-10-18 14:10:43', '2026-10-18 06:00:43'),
  (62, 'eldrickb00@gmail.com', '420924', '2026-10-18 14:10:46', '2026-10-18 06:00:46'),
  (63, 'karlmartinez475@gmail.com', '238737', '2026-10-18 14:10:58', '2026-10-18 06:00:58'),
  (64, 'karlmartinez475@gmail.com', '222650', '2026-10-18 14:10:58', '2026-10-18 06:00:59'),
  (65, 'karlmartinez475@gmail.com', '202460', '2026-10-18 14:11:04', '2026-10-18 06:01:04'),
  (66, 'karlmartinez475@gmail.com', '318948', '2026-10-18 14:11:12', '2026-10-18 06:01:12'),
  (67, 'karlmartinez475@gmail.com', '118224', '2026-10-18 14:11:12', '2026-10-18 06:01:12'),
  (68, 'karlmartinez475@gmail.com', '954569', '2026-10-18 14:11:13', '2026-10-18 06:01:13'),
  (69, 'chester292005@gmail.com', '487199', '2026-10-18 14:11:34', '2026-10-18 06:01:35'),
  (70, 'karlmartinez475@gmail.com', '549431', '2026-10-18 14:11:48', '2026-10-18 06:01:48'),
  (71, 'yckotoshihernandez8@gmail.com', '720894', '2026-10-18 14:11:54', '2026-10-18 06:01:54'),
  (72, 'karlmartinez475@gmail.com', '245280', '2026-10-18 14:12:32', '2026-10-18 06:02:32'),
  (73, 'karlmartinez475@gmail.com', '731711', '2026-10-18 14:12:32', '2026-10-18 06:02:32'),
  (74, 'eldrickb00@gmail.com', '230217', '2026-10-18 14:19:47', '2026-10-18 06:09:47'),
  (75, 'jodelynmarvilla@gmail.com', '173865', '2026-10-18 14:32:05', '2026-10-18 06:22:05'),
  (76, 'jankrishnamiranda21@gmail.com', '345193', '2026-10-18 14:37:10', '2026-10-18 06:27:10'),
  (77, 'morenongkups@gmail.com', '456650', '2026-10-18 14:39:19', '2026-10-18 06:29:19'),
  (78, 'karlmartinez475@gmail.com', '150240', '2026-10-18 14:41:57', '2026-10-18 06:31:57'),
  (79, 'eldrickb00@gmail.com', '405465', '2026-10-18 14:45:53', '2026-10-18 06:35:53'),
  (80, 'morenongkups@gmail.com', '421250', '2026-10-18 14:46:01', '2026-10-18 06:36:01'),
  (81, 'morenongkups@gmail.com', '630288', '2026-10-18 15:00:20', '2026-10-18 06:50:20'),
  (82, 'sanielken2@gmail.com', '461668', '2026-10-18 15:01:02', '2026-10-18 06:51:02'),
  (83, 'sanielken2@gmail.com', '838598', '2026-10-18 15:26:21', '2026-10-18 07:16:21'),
  (84, 'sanielken2@gmail.com', '225395', '2026-10-18 15:27:05', '2026-10-18 07:17:05'),
  (85, 'yckotoshihernandez8@gmail.com', '435813', '2026-10-18 15:29:01', '2026-10-18 07:19:01'),
  (86, 'yckotoshihernandez8@gmail.com', '216995', '2026-10-18 15:30:47', '2026-10-18 07:20:47');

-- Table structure for `topups`
DROP TABLE IF EXISTS `topups`;
CREATE TABLE IF NOT EXISTS topups (
    topup_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT,
    payment_mode VARCHAR(50) DEFAULT 'gcash',
    method VARCHAR(50),
    gcash_number VARCHAR(30),
    gcash_owner VARCHAR(100),
    amount DECIMAL(10, 2) NOT NULL,
    reference_number VARCHAR(100),
    screenshot_path VARCHAR(255),
    proof_image VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_topups_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dumping data for `topups` (12 rows)
INSERT INTO `topups` (`topup_id`, `student_id`, `payment_mode`, `method`, `gcash_number`, `gcash_owner`, `amount`, `reference_number`, `screenshot_path`, `proof_image`, `status`, `created_at`) VALUES
  (1, 2, 'gcash', NULL, '09756739146', 'Sample Owner Name', 200, '09276879042', NULL, 'inbound6210269244366378536.jpg', 'completed', '2026-10-16 09:43:00'),
  (2, 2, 'gcash', NULL, '09756739146', 'Scuola dei Bambini Canteen', 100, '1234 543 778896', NULL, '2_1792147159_images_20.jpg', 'completed', '2026-10-16 18:39:23'),
  (3, 2, 'gcash', NULL, '09756739146', 'Scuola dei Bambini Canteen', 500, '1234 543 778445', NULL, '2_1792241750_5aebf10d-ee1b-48c7-a316-e9aa84b86d74.jpg', 'completed', '2026-10-17 20:55:50'),
  (4, 2, 'gcash', NULL, '09756739146', 'Scuola dei Bambini Canteen', 1000, '4334 543 778896', NULL, '2_1792255666_5aebf10d-ee1b-48c7-a316-e9aa84b86d74.jpg', 'completed', '2026-10-18 00:47:46'),
  (5, 3, 'gcash', NULL, '09756739146', 'Scuola dei Bambini Canteen', 38000, '38000', NULL, '3_1792303183_inbound7737694480148803252.jpg', 'completed', '2026-10-18 13:59:43'),
  (6, 4, 'gcash', NULL, '09756739146', 'Scuola dei Bambini Canteen', 500, '1223 223 456374', NULL, '4_1792303371_inbound8131250410252593316.jpg', 'completed', '2026-10-18 14:02:51'),
  (7, 6, 'gcash', NULL, '09756739146', 'Scuola dei Bambini Canteen', 500000, '09756739146', NULL, '6_1792303436_inbound2864749342147771454.jpg', 'completed', '2026-10-18 14:03:56'),
  (8, 5, 'gcash', NULL, '09756739146', 'Scuola dei Bambini Canteen', 500, '09284716412', NULL, '5_1792303477_inbound7309779008448076208.jpg', 'completed', '2026-10-18 14:04:37'),
  (9, 4, 'gcash', NULL, '09756739146', 'Scuola dei Bambini Canteen', 5000, '2441 345 765432', NULL, '4_1792303501_inbound2613257535254962851.jpg', 'completed', '2026-10-18 14:05:01'),
  (10, 7, 'gcash', NULL, '09756739146', 'Scuola dei Bambini Canteen', 100000, '0123456789123', NULL, '7_1792303516_1000011765.jpg', 'completed', '2026-10-18 14:05:16'),
  (11, 6, 'gcash', NULL, '09756739146', 'Scuola dei Bambini Canteen', 125, '09945758650', NULL, '6_1792308219_980.jpg', 'completed', '2026-10-18 15:23:39'),
  (12, 2, 'gcash', NULL, '09756739146', 'Scuola dei Bambini Canteen', 200, '1023 134 106576', NULL, '2_1792322873_Screenshot_573.png', 'completed', '2026-10-18 19:27:53');

-- Table structure for `transactions`
DROP TABLE IF EXISTS `transactions`;
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT,
    staff_id INT,
    admin_id INT,
    customer_name VARCHAR(100),
    amount DECIMAL(10, 2) NOT NULL,
    previous_balance DECIMAL(10, 2),
    new_balance DECIMAL(10, 2),
    status VARCHAR(20) DEFAULT 'completed',
    remarks TEXT,
    type VARCHAR(30) DEFAULT 'purchase',
    payment_mode VARCHAR(30) DEFAULT 'cash',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_transactions_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE SET NULL,
    CONSTRAINT fk_transactions_staff FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL,
    CONSTRAINT fk_transactions_admin FOREIGN KEY (admin_id) REFERENCES admins(admin_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dumping data for `transactions` (39 rows)
INSERT INTO `transactions` (`transaction_id`, `student_id`, `staff_id`, `admin_id`, `customer_name`, `amount`, `previous_balance`, `new_balance`, `status`, `remarks`, `type`, `payment_mode`, `created_at`) VALUES
  (1, 1, 1, NULL, NULL, 15, 100, 85, 'completed', 'Merienda', 'purchase', 'cashless', '2026-10-16 18:31:34'),
  (2, 2, NULL, NULL, NULL, 200, 0, 200, 'completed', 'GCash Top-Up (Ref: 09276879042)', 'topup', 'gcash', '2026-10-16 09:43:00'),
  (3, 2, NULL, NULL, NULL, 100, 0, 100, 'completed', 'GCash Top-Up (Ref: 1234 543 778896)', 'topup', 'gcash', '2026-10-16 18:39:23'),
  (4, 2, 2, NULL, NULL, 145, 300, 155, 'completed', NULL, 'purchase', 'wallet', '2026-10-16 19:26:54'),
  (5, 2, 2, NULL, NULL, 115, 155, 40, 'completed', NULL, 'purchase', 'wallet', '2026-10-17 20:18:59'),
  (6, 1, 2, NULL, NULL, 25, 85, 60, 'completed', NULL, 'purchase', 'wallet', '2026-10-17 20:36:31'),
  (7, NULL, NULL, NULL, 'Visitor', 25, NULL, NULL, 'completed', NULL, 'purchase', 'GCash', '2026-10-17 20:41:25'),
  (8, NULL, 2, NULL, 'batman', 200, NULL, NULL, 'completed', NULL, 'purchase', 'Cash', '2026-10-17 20:51:19'),
  (9, 2, NULL, 2, NULL, 500, 40, 540, 'completed', 'GCash Top-Up (Ref: 1234 543 778445)', 'topup', 'gcash', '2026-10-17 20:58:15'),
  (10, 2, 2, NULL, NULL, 375, 540, 165, 'completed', NULL, 'purchase', 'wallet', '2026-10-17 21:17:58'),
  (11, 2, 2, NULL, NULL, 75, 165, 90, 'completed', NULL, 'purchase', 'wallet', '2026-10-17 22:53:29'),
  (12, 2, 2, NULL, NULL, 90, 90, 0, 'completed', NULL, 'purchase', 'wallet', '2026-10-17 22:56:28'),
  (13, 1, 2, NULL, NULL, 25, 60, 35, 'completed', NULL, 'purchase', 'wallet', '2026-10-17 22:59:41'),
  (14, NULL, 2, NULL, 'Walk-in (GCash)', 170, NULL, NULL, 'completed', NULL, 'purchase', 'gcash', '2026-10-17 23:45:38'),
  (15, NULL, 2, NULL, 'Walk-in (Cash)', 90, NULL, NULL, 'completed', 'Cash: ₱100.00, Sukli: ₱10.00', 'purchase', 'cash', '2026-10-17 23:46:26'),
  (16, NULL, 2, NULL, 'Walk-in (GCash)', 45, NULL, NULL, 'completed', '3× Bottled Water', 'purchase', 'gcash', '2026-10-17 23:48:06'),
  (17, NULL, 2, NULL, 'Walk-in (Cash)', 15, NULL, NULL, 'completed', '1× Bottled Water (Cash: ₱20.00, Sukli: ₱5.00)', 'purchase', 'cash', '2026-10-18 00:46:42'),
  (18, 2, NULL, 2, NULL, 1000, 0, 1000, 'completed', 'GCash Top-Up (Ref: 4334 543 778896)', 'topup', 'gcash', '2026-10-18 00:47:55'),
  (19, 2, 2, NULL, NULL, 75, 1000, 925, 'completed', '1× Tapsilog', 'purchase', 'wallet', '2026-10-18 00:48:25'),
  (20, 2, 2, NULL, NULL, 150, 925, 775, 'completed', '2× Tapsilog', 'purchase', 'wallet', '2026-10-18 13:29:49'),
  (21, 3, NULL, 2, NULL, 38000, 0, 38000, 'completed', 'GCash Top-Up (Ref: 38000)', 'topup', 'gcash', '2026-10-18 14:00:19'),
  (22, 4, NULL, 2, NULL, 500, 0, 500, 'completed', 'GCash Top-Up (Ref: 1223 223 456374)', 'topup', 'gcash', '2026-10-18 14:03:22'),
  (23, 6, NULL, 2, NULL, 500000, 0, 500000, 'completed', 'GCash Top-Up (Ref: 09756739146)', 'topup', 'gcash', '2026-10-18 14:04:30'),
  (24, 5, NULL, 2, NULL, 500, 0, 500, 'completed', 'GCash Top-Up (Ref: 09284716412)', 'topup', 'gcash', '2026-10-18 14:04:49'),
  (25, 4, NULL, 2, NULL, 5000, 500, 5500, 'completed', 'GCash Top-Up (Ref: 2441 345 765432)', 'topup', 'gcash', '2026-10-18 14:05:10'),
  (26, 7, NULL, 2, NULL, 100000, 0, 100000, 'completed', 'GCash Top-Up (Ref: 0123456789123)', 'topup', 'gcash', '2026-10-18 14:05:40'),
  (27, 4, 2, NULL, NULL, 300, 5500, 5200, 'completed', '4× Tapsilog', 'purchase', 'wallet', '2026-10-18 14:06:31'),
  (28, 3, 2, NULL, NULL, 75, 38000, 37925, 'completed', '1× Tapsilog', 'purchase', 'wallet', '2026-10-18 14:06:59'),
  (29, 6, 2, NULL, NULL, 125, 500000, 499875, 'completed', '5× Teh Ais', 'purchase', 'wallet', '2026-10-18 14:07:46'),
  (30, 7, 2, NULL, NULL, 200, 100000, 99800, 'completed', '2× Tiramisu Cup', 'purchase', 'wallet', '2026-10-18 14:08:55'),
  (31, 3, 2, NULL, NULL, 45, 37925, 37880, 'completed', '3× Bottled Water', 'purchase', 'wallet', '2026-10-18 14:10:21'),
  (32, 1, 2, NULL, NULL, 150, 35, 35, 'completed', '2× Tapsilog', 'purchase', 'cash', '2026-10-18 14:11:50'),
  (33, NULL, 2, NULL, 'Walk-in (Cash)', 3000, NULL, NULL, 'completed', NULL, 'purchase', 'cash', '2026-10-18 14:13:15'),
  (34, 7, 2, NULL, NULL, 390, 99800, 99410, 'completed', '2× Chicken Sandwich, 3× Tiramisu Cup', 'purchase', 'wallet', '2026-10-18 14:34:55'),
  (35, NULL, 2, NULL, 'Walk-in (Cash)', 550, NULL, NULL, 'completed', '4× Tiramisu Cup, 2× Tapsilog (Cash: ₱550.00, Sukli: ₱0.00)', 'purchase', 'cash', '2026-10-18 15:12:28'),
  (36, 6, NULL, 2, NULL, 125, 499875, 500000, 'completed', 'GCash Top-Up (Ref: 09945758650)', 'topup', 'gcash', '2026-10-18 15:23:51'),
  (37, 2, 2, NULL, NULL, 25, 775, 750, 'completed', '1× Teh Ais', 'purchase', 'wallet', '2026-10-18 19:23:37'),
  (38, 2, NULL, 2, NULL, 200, 750, 950, 'completed', 'GCash Top-Up (Ref: 1023 134 106576)', 'topup', 'gcash', '2026-10-18 19:28:28'),
  (39, 3, 2, NULL, NULL, 375, 37880, 37505, 'completed', '5× Tapsilog', 'purchase', 'wallet', '2026-10-18 19:48:20');

-- Table structure for `unregistered_transactions`
DROP TABLE IF EXISTS `unregistered_transactions`;
CREATE TABLE IF NOT EXISTS unregistered_transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    staff_id INT,
    customer_name VARCHAR(100),
    contact_number VARCHAR(20),
    amount DECIMAL(10, 2),
    payment_mode VARCHAR(30) DEFAULT 'cash',
    qr_code VARCHAR(255),
    status VARCHAR(20) DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_unregistered_staff FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table structure for `staff_totals`
DROP TABLE IF EXISTS `staff_totals`;
CREATE TABLE IF NOT EXISTS staff_totals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    staff_id INT,
    amount DECIMAL(10, 2),
    mode VARCHAR(30),
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_staff_totals_staff FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table structure for `canteen_products`
DROP TABLE IF EXISTS `canteen_products`;
CREATE TABLE IF NOT EXISTS canteen_products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255) DEFAULT 'Fresh canteen item',
    category VARCHAR(30) DEFAULT 'Main',
    price DECIMAL(10, 2) NOT NULL,
    stock INT DEFAULT 50,
    image_path VARCHAR(255),
    icon VARCHAR(20) DEFAULT '🍽️',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dumping data for `canteen_products` (2 rows)
INSERT INTO `canteen_products` (`product_id`, `name`, `description`, `category`, `price`, `stock`, `image_path`, `icon`, `created_at`) VALUES
  (1, 'Beef Steak', 'Beef', 'Main', 250, 45, 'images/products/prod_1792303769_9f3770.png', '🍱', '2026-10-18 06:09:29'),
  (2, 'rtr', 'Freshly prepared canteen item', 'Main', 678, 30, 'images/products/prod_1792304864_4ed33f.png', '🍱', '2026-10-18 06:27:44');

SET FOREIGN_KEY_CHECKS = 1;
