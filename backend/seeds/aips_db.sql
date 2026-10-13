-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Jul 15, 2026 at 04:59 AM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `aips_db`
--

-- --------------------------------------------------------

--
-- Table structure for table `admin_user`
--

CREATE TABLE `admin_user` (
  `admin_id` bigint(20) NOT NULL,
  `username` varchar(255) NOT NULL,
  `password` varchar(255) NOT NULL,
  `role` enum('Admin','Security') NOT NULL,
  `email` varchar(255) NOT NULL,
  `location` enum('west','east','eastwest') DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `admin_user`
--

INSERT INTO `admin_user` (`admin_id`, `username`, `password`, `role`, `email`, `location`) VALUES
(1, 'Admin', '$2b$12$MD/XDrreVR2c1I5B99oEIO7tSgxUhENJUDU78OVulb7ZYxgeNh2Pq', 'Admin', 'admin@mattel.com', 'west');

-- --------------------------------------------------------

--
-- Table structure for table `analytics_data`
--

CREATE TABLE `analytics_data` (
  `analytics_id` bigint(20) NOT NULL,
  `zone_id` bigint(20) NOT NULL,
  `record_date` date NOT NULL,
  `predicted_demand` int(11) NOT NULL DEFAULT 0,
  `predicted_employee` int(11) NOT NULL DEFAULT 0,
  `predicted_vendor` int(11) NOT NULL DEFAULT 0,
  `predicted_visitor` int(11) NOT NULL DEFAULT 0,
  `peak_hour_start` time NOT NULL,
  `peak_hour_end` time NOT NULL,
  `avg_occupancy_rate` float NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `period_type` varchar(10) NOT NULL DEFAULT 'daily',
  `area_code` varchar(10) DEFAULT NULL,
  `period_label` varchar(20) DEFAULT NULL,
  `predicted_available` int(11) DEFAULT NULL,
  `status` varchar(10) DEFAULT 'Normal'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `entry_exit_log`
--

CREATE TABLE `entry_exit_log` (
  `log_id` bigint(20) NOT NULL,
  `session_id` bigint(20) DEFAULT NULL,
  `admin_id` bigint(20) DEFAULT NULL,
  `zone_id` bigint(20) NOT NULL,
  `event_type` enum('Entry','Exit','Denied') NOT NULL,
  `plate_detected` varchar(255) NOT NULL,
  `confidence_score` float DEFAULT NULL,
  `event_timestamp` datetime NOT NULL DEFAULT current_timestamp(),
  `auth_method` enum('AI_LPR','KPK_Scan','Manual_Security') NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `member`
--

CREATE TABLE `member` (
  `member_id` bigint(20) NOT NULL,
  `kpk_number` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `registered_plant` enum('west','east','eastwest') NOT NULL DEFAULT 'west',
  `location` varchar(255) DEFAULT NULL,
  `category` enum('Employee','Vendor','Visitor') NOT NULL DEFAULT 'Employee',
  `sim_exp` date DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `member`
--

INSERT INTO `member` (`member_id`, `kpk_number`, `name`, `registered_plant`, `location`, `category`, `sim_exp`, `created_at`, `updated_at`) VALUES
(1, 'KPK001', 'Andi Pratama', 'west', NULL, 'Employee', '2026-08-15', '2026-07-11 19:19:18', '2026-07-11 19:19:18'),
(2, 'KPK002', 'Budi Santoso', 'east', NULL, 'Employee', '2027-03-20', '2026-07-11 19:22:31', '2026-07-11 19:22:31'),
(3, 'KPK003', 'Citra Dewi', 'west', NULL, 'Employee', '2025-11-30', '2026-07-11 19:22:31', '2026-07-11 19:22:31'),
(4, 'KPK004', 'Dian Wahyuni', 'eastwest', NULL, 'Employee', '2026-06-01', '2026-07-11 19:22:31', '2026-07-11 19:22:31'),
(5, 'KPK005', 'Eko Setiawan', 'east', NULL, 'Vendor', '2026-09-15', '2026-07-11 19:22:31', '2026-07-11 19:22:31'),
(6, 'KPK006', 'Fitri Handayani', 'west', NULL, 'Employee', '2027-01-10', '2026-07-11 19:22:31', '2026-07-11 19:22:31'),
(7, 'KPK007', 'Gilang Ramadhan', 'west', NULL, 'Employee', '2025-07-22', '2026-07-11 19:22:31', '2026-07-11 19:22:31'),
(8, 'KPK008', 'Hendra Kurniawan', 'east', NULL, 'Vendor', '2026-04-18', '2026-07-11 19:22:31', '2026-07-11 19:22:31'),
(9, 'KPK009', 'Indah Sari', 'eastwest', NULL, 'Employee', '2026-12-05', '2026-07-11 19:22:31', '2026-07-11 19:22:31'),
(10, 'KPK010', 'Joko Widodo', 'west', NULL, 'Employee', '2027-05-10', '2026-07-11 19:22:31', '2026-07-11 19:22:31'),
(11, 'KPK011', 'Kartika Sari', 'east', NULL, 'Employee', '2026-02-14', '2026-07-11 19:22:31', '2026-07-11 19:22:31'),
(12, 'KPK012', 'Lukman Hakim', 'west', NULL, 'Vendor', '2025-09-30', '2026-07-11 19:22:31', '2026-07-11 19:22:31'),
(13, 'KPK013', 'Maya Angelica', 'east', NULL, 'Visitor', '2026-08-20', '2026-07-11 19:22:31', '2026-07-11 19:22:31'),
(14, 'KPK014', 'Nanda Prasetya', 'eastwest', NULL, 'Employee', '2026-11-25', '2026-07-11 19:22:31', '2026-07-11 19:22:31'),
(15, 'KPK015', 'Oktavia Putri', 'west', NULL, 'Employee', '2027-03-08', '2026-07-11 19:22:31', '2026-07-11 19:22:31');

-- --------------------------------------------------------

--
-- Table structure for table `occupancy_snapshot`
--

CREATE TABLE `occupancy_snapshot` (
  `snapshot_id` bigint(20) NOT NULL,
  `zone_id` bigint(20) NOT NULL,
  `recorded_at` datetime NOT NULL,
  `total_capacity` int(11) NOT NULL,
  `total_occupied` int(11) NOT NULL,
  `total_available` int(11) NOT NULL,
  `overall_rate_pct` float NOT NULL,
  `employee_used` int(11) NOT NULL DEFAULT 0,
  `employee_total` int(11) NOT NULL DEFAULT 0,
  `vendor_used` int(11) NOT NULL DEFAULT 0,
  `vendor_total` int(11) NOT NULL DEFAULT 0,
  `visitor_used` int(11) NOT NULL DEFAULT 0,
  `visitor_total` int(11) NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `parking_session`
--

CREATE TABLE `parking_session` (
  `session_id` bigint(20) NOT NULL,
  `vehicle_id` bigint(20) NOT NULL,
  `zone_id` bigint(20) NOT NULL,
  `entry_time` datetime NOT NULL DEFAULT current_timestamp(),
  `exit_time` datetime DEFAULT NULL,
  `booking_reference` varchar(255) DEFAULT NULL,
  `status` enum('IN','OUT') NOT NULL DEFAULT 'IN'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `parking_slot`
--

CREATE TABLE `parking_slot` (
  `slot_id` bigint(20) NOT NULL,
  `zone_id` bigint(20) NOT NULL,
  `coordinates_polygon` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`coordinates_polygon`)),
  `slot_label` varchar(255) NOT NULL,
  `category` enum('Employee','Vendor','Visitor') NOT NULL DEFAULT 'Employee',
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `current_status` enum('Available','Occupied') NOT NULL DEFAULT 'Available'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `parking_zone`
--

CREATE TABLE `parking_zone` (
  `zone_id` bigint(20) NOT NULL,
  `zone_key` varchar(50) NOT NULL,
  `zone_name` varchar(255) NOT NULL,
  `total_capacity` int(11) NOT NULL,
  `employee_capacity` int(11) NOT NULL DEFAULT 0,
  `vendor_capacity` int(11) NOT NULL DEFAULT 0,
  `visitor_capacity` int(11) NOT NULL DEFAULT 0,
  `used_capacity` int(11) NOT NULL DEFAULT 0,
  `employee_used` int(11) NOT NULL DEFAULT 0,
  `vendor_used` int(11) NOT NULL DEFAULT 0,
  `visitor_used` int(11) NOT NULL DEFAULT 0,
  `camera_ids` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`camera_ids`)),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `parking_zone`
--

INSERT INTO `parking_zone` (`zone_id`, `zone_key`, `zone_name`, `total_capacity`, `employee_capacity`, `vendor_capacity`, `visitor_capacity`, `used_capacity`, `employee_used`, `vendor_used`, `visitor_used`, `camera_ids`, `updated_at`) VALUES
(1, 'west', 'West Plant', 130, 100, 20, 10, 0, 0, 0, 0, '[]', '2026-07-11 19:15:49'),
(2, 'east', 'East Plant', 130, 100, 20, 10, 0, 0, 0, 0, '[]', '2026-07-11 19:15:49'),
(3, 'eastwest', 'East & West Plant', 65, 50, 10, 5, 0, 0, 0, 0, '[]', '2026-07-11 19:15:49');

-- --------------------------------------------------------

--
-- Table structure for table `pending_plate_review`
--

CREATE TABLE `pending_plate_review` (
  `review_id` bigint(20) NOT NULL,
  `zone_id` bigint(20) NOT NULL,
  `track_id` int(11) DEFAULT NULL,
  `plate_guess` varchar(20) DEFAULT NULL,
  `confidence` float DEFAULT NULL,
  `vehicle_type` varchar(50) DEFAULT NULL,
  `event_type` enum('entry','exit') NOT NULL,
  `image_paths` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`image_paths`)),
  `status` varchar(20) NOT NULL DEFAULT 'queued',
  `captured_at` datetime NOT NULL DEFAULT current_timestamp(),
  `resolved_at` datetime DEFAULT NULL,
  `resolved_by` bigint(20) DEFAULT NULL,
  `resulting_log_id` bigint(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `vehicle`
--

CREATE TABLE `vehicle` (
  `vehicle_id` bigint(20) NOT NULL,
  `member_id` bigint(20) DEFAULT NULL,
  `plate_number` varchar(255) NOT NULL,
  `vehicle_type` varchar(255) NOT NULL,
  `stnk_exp` date DEFAULT NULL,
  `user_category` enum('Member','Visitor') NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `vehicle`
--

INSERT INTO `vehicle` (`vehicle_id`, `member_id`, `plate_number`, `vehicle_type`, `stnk_exp`, `user_category`) VALUES
(1, 1, 'B 1234 ABC', 'Car', '2026-08-15', 'Member'),
(2, 1, 'B 5678 XYZ', 'Car', NULL, 'Member'),
(3, 2, 'D 4321 DEF', 'Car', NULL, 'Member'),
(4, 3, 'B 9876 GHI', 'Car', NULL, 'Member'),
(5, 4, 'F 1111 JKL', 'Car', NULL, 'Member'),
(6, 4, 'F 2222 MNO', 'Car', NULL, 'Member'),
(7, 5, 'B 3333 PQR', 'Car', NULL, 'Member'),
(8, 6, 'E 4444 STU', 'Car', NULL, 'Member'),
(9, 7, 'B 5555 VWX', 'Car', NULL, 'Member'),
(10, 8, 'D 6666 YZA', 'Car', NULL, 'Member'),
(11, 9, 'B 7777 BCD', 'Car', NULL, 'Member'),
(12, 10, 'B 8888 EFG', 'Car', NULL, 'Member'),
(13, 11, 'D 9999 HIJ', 'Car', NULL, 'Member'),
(14, 12, 'B 1010 KLM', 'Car', NULL, 'Member'),
(15, 12, 'B 2020 NOP', 'Car', NULL, 'Member'),
(16, 13, 'F 3030 QRS', 'Car', NULL, 'Member'),
(17, 14, 'B 4040 TUV', 'Car', NULL, 'Member'),
(18, 15, 'B 5050 WXY', 'Car', NULL, 'Member');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `admin_user`
--
ALTER TABLE `admin_user`
  ADD PRIMARY KEY (`admin_id`),
  ADD UNIQUE KEY `username` (`username`),
  ADD UNIQUE KEY `email` (`email`);

--
-- Indexes for table `analytics_data`
--
ALTER TABLE `analytics_data`
  ADD PRIMARY KEY (`analytics_id`),
  ADD KEY `zone_id` (`zone_id`),
  ADD KEY `idx_analytics_date` (`record_date`),
  ADD KEY `idx_analytics_period_area` (`period_type`,`area_code`),
  ADD UNIQUE KEY `uq_analytics_zone_date_area` (`zone_id`,`record_date`,`period_type`,`area_code`);

--
-- Indexes for table `entry_exit_log`
--
ALTER TABLE `entry_exit_log`
  ADD PRIMARY KEY (`log_id`),
  ADD KEY `session_id` (`session_id`),
  ADD KEY `admin_id` (`admin_id`),
  ADD KEY `idx_log_zone` (`zone_id`);

--
-- Indexes for table `member`
--
ALTER TABLE `member`
  ADD PRIMARY KEY (`member_id`),
  ADD UNIQUE KEY `kpk_number` (`kpk_number`);

--
-- Indexes for table `occupancy_snapshot`
--
ALTER TABLE `occupancy_snapshot`
  ADD PRIMARY KEY (`snapshot_id`),
  ADD KEY `idx_snapshot_zone_time` (`zone_id`,`recorded_at`);

--
-- Indexes for table `parking_session`
--
ALTER TABLE `parking_session`
  ADD PRIMARY KEY (`session_id`),
  ADD KEY `vehicle_id` (`vehicle_id`),
  ADD KEY `zone_id` (`zone_id`);

--
-- Indexes for table `parking_slot`
--
ALTER TABLE `parking_slot`
  ADD PRIMARY KEY (`slot_id`),
  ADD UNIQUE KEY `uq_slot_label_zone` (`zone_id`,`slot_label`);

--
-- Indexes for table `parking_zone`
--
ALTER TABLE `parking_zone`
  ADD PRIMARY KEY (`zone_id`),
  ADD UNIQUE KEY `zone_key` (`zone_key`);

--
-- Indexes for table `pending_plate_review`
--
ALTER TABLE `pending_plate_review`
  ADD PRIMARY KEY (`review_id`),
  ADD KEY `zone_id` (`zone_id`),
  ADD KEY `resolved_by` (`resolved_by`),
  ADD KEY `resulting_log_id` (`resulting_log_id`),
  ADD KEY `idx_review_status` (`status`),
  ADD KEY `idx_review_captured` (`captured_at`);

--
-- Indexes for table `vehicle`
--
ALTER TABLE `vehicle`
  ADD PRIMARY KEY (`vehicle_id`),
  ADD UNIQUE KEY `plate_number` (`plate_number`),
  ADD KEY `member_id` (`member_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `admin_user`
--
ALTER TABLE `admin_user`
  MODIFY `admin_id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- AUTO_INCREMENT for table `analytics_data`
--
ALTER TABLE `analytics_data`
  MODIFY `analytics_id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `entry_exit_log`
--
ALTER TABLE `entry_exit_log`
  MODIFY `log_id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=33;

--
-- AUTO_INCREMENT for table `member`
--
ALTER TABLE `member`
  MODIFY `member_id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=16;

--
-- AUTO_INCREMENT for table `occupancy_snapshot`
--
ALTER TABLE `occupancy_snapshot`
  MODIFY `snapshot_id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `parking_session`
--
ALTER TABLE `parking_session`
  MODIFY `session_id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `parking_slot`
--
ALTER TABLE `parking_slot`
  MODIFY `slot_id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `parking_zone`
--
ALTER TABLE `parking_zone`
  MODIFY `zone_id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `pending_plate_review`
--
ALTER TABLE `pending_plate_review`
  MODIFY `review_id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `vehicle`
--
ALTER TABLE `vehicle`
  MODIFY `vehicle_id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=19;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `analytics_data`
--
ALTER TABLE `analytics_data`
  ADD CONSTRAINT `analytics_data_ibfk_1` FOREIGN KEY (`zone_id`) REFERENCES `parking_zone` (`zone_id`);

--
-- Constraints for table `entry_exit_log`
--
ALTER TABLE `entry_exit_log`
  ADD CONSTRAINT `entry_exit_log_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `parking_session` (`session_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `entry_exit_log_ibfk_2` FOREIGN KEY (`admin_id`) REFERENCES `admin_user` (`admin_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `entry_exit_log_ibfk_3` FOREIGN KEY (`zone_id`) REFERENCES `parking_zone` (`zone_id`),
  ADD CONSTRAINT `fk_log_zone` FOREIGN KEY (`zone_id`) REFERENCES `parking_zone` (`zone_id`);

--
-- Constraints for table `occupancy_snapshot`
--
ALTER TABLE `occupancy_snapshot`
  ADD CONSTRAINT `occupancy_snapshot_ibfk_1` FOREIGN KEY (`zone_id`) REFERENCES `parking_zone` (`zone_id`);

--
-- Constraints for table `parking_session`
--
ALTER TABLE `parking_session`
  ADD CONSTRAINT `parking_session_ibfk_1` FOREIGN KEY (`vehicle_id`) REFERENCES `vehicle` (`vehicle_id`),
  ADD CONSTRAINT `parking_session_ibfk_2` FOREIGN KEY (`zone_id`) REFERENCES `parking_zone` (`zone_id`);

--
-- Constraints for table `parking_slot`
--
ALTER TABLE `parking_slot`
  ADD CONSTRAINT `parking_slot_ibfk_1` FOREIGN KEY (`zone_id`) REFERENCES `parking_zone` (`zone_id`) ON DELETE CASCADE;

--
-- Constraints for table `pending_plate_review`
--
ALTER TABLE `pending_plate_review`
  ADD CONSTRAINT `pending_plate_review_ibfk_1` FOREIGN KEY (`zone_id`) REFERENCES `parking_zone` (`zone_id`),
  ADD CONSTRAINT `pending_plate_review_ibfk_2` FOREIGN KEY (`resolved_by`) REFERENCES `admin_user` (`admin_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `pending_plate_review_ibfk_3` FOREIGN KEY (`resulting_log_id`) REFERENCES `entry_exit_log` (`log_id`) ON DELETE SET NULL;

--
-- Constraints for table `vehicle`
--
ALTER TABLE `vehicle`
  ADD CONSTRAINT `vehicle_ibfk_1` FOREIGN KEY (`member_id`) REFERENCES `member` (`member_id`) ON DELETE SET NULL;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
