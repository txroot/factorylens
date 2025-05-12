-- phpMyAdmin SQL Dump
-- version 5.2.2
-- https://www.phpmyadmin.net/
--
-- Host: db
-- Tempo de geração: 12-Maio-2025 às 08:54
-- Versão do servidor: 11.7.2-MariaDB-ubu2404
-- versão do PHP: 8.2.28

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de dados: `factorylens`
--

-- --------------------------------------------------------

--
-- Estrutura da tabela `actions`
--

CREATE TABLE `actions` (
  `id` int(11) NOT NULL,
  `name` varchar(120) NOT NULL,
  `description` text DEFAULT NULL,
  `chain` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`chain`)),
  `enabled` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Extraindo dados da tabela `actions`
--

INSERT INTO `actions` (`id`, `name`, `description`, `chain`, `enabled`, `created_at`, `updated_at`) VALUES
(13, 'Button for Camera Snapshot', 'Once we short press the module Button I1, is triggered a request for a snapshot.', '[{\"device_id\": 7, \"source\": \"io\", \"topic\": \"input_event/1\", \"cmp\": \"==\", \"match\": {\"value\": \"S\"}, \"poll_topic\": \"\", \"poll_payload\": \"\", \"poll_interval\": 0, \"poll_interval_unit\": \"ms\"}, {\"device_id\": 13, \"topic\": \"snapshot/exe\", \"command\": \"jpg\", \"ignore_input\": false, \"result_topic\": \"snapshot\", \"result_payload\": {}, \"timeout\": 5, \"timeout_unit\": \"sec\"}]', 1, '2025-05-11 10:02:00', '2025-05-11 18:43:09'),
(14, 'Snapshot detected', 'Once a new snapshopt is detected we request the saving in local storage.', '[{\"device_id\": 13, \"source\": \"io\", \"topic\": \"snapshot\", \"cmp\": \"==\", \"match\": {\"value\": \"jpg\"}, \"poll_topic\": \"\", \"poll_payload\": \"\", \"poll_interval\": 0, \"poll_interval_unit\": \"ms\"}, {\"device_id\": 2, \"topic\": \"file/image/create\", \"command\": \"$IF\", \"ignore_input\": false, \"result_topic\": \"file/created\", \"result_payload\": {}, \"timeout\": 2, \"timeout_unit\": \"sec\"}, {\"device_id\": 7, \"topic\": \"relay/0/command\", \"command\": \"on\", \"result_topic\": \"relay/0\", \"timeout\": 10, \"timeout_unit\": \"sec\", \"cmp\": \"==\", \"match\": {\"value\": \"success\"}, \"branch\": \"success\", \"result_payload\": {}}, {\"device_id\": 7, \"topic\": \"relay/1/command\", \"command\": \"on\", \"result_topic\": \"relay/1\", \"timeout\": 10, \"timeout_unit\": \"sec\", \"cmp\": \"==\", \"match\": {\"value\": \"error\"}, \"branch\": \"error\", \"result_payload\": {}}]', 1, '2025-05-11 11:26:10', '2025-05-11 18:44:11'),
(15, 'File Saving Success', 'Success on saving file', '[{\"device_id\": 2, \"source\": \"io\", \"topic\": \"file/created\", \"cmp\": \"==\", \"match\": {\"value\": \"success\"}, \"poll_topic\": \"\", \"poll_payload\": \"\", \"poll_interval\": 0, \"poll_interval_unit\": \"ms\"}, {\"device_id\": 7, \"topic\": \"relay/1/command\", \"command\": \"on\", \"ignore_input\": false, \"result_topic\": \"relay/1\", \"result_payload\": {}, \"timeout\": 2, \"timeout_unit\": \"sec\"}]', 1, '2025-05-11 17:10:44', '2025-05-11 18:43:52'),
(16, 'Button Short Press Validation', 'Led is used to let user know a Short Press was detected in Button I1', '[{\"device_id\": 7, \"source\": \"io\", \"topic\": \"input_event/1\", \"cmp\": \"==\", \"match\": {\"value\": \"S\"}, \"poll_topic\": \"\", \"poll_payload\": \"\", \"poll_interval\": 0, \"poll_interval_unit\": \"ms\"}, {\"device_id\": 7, \"topic\": \"relay/0/command\", \"command\": \"on\", \"ignore_input\": false, \"result_topic\": \"relay/0\", \"result_payload\": {\"options\": [{\"label\": \"Relay 0 State\", \"tooltip\": \"Current on/off state of relay 0\", \"hint\": \"Use Evaluate to check on/off\", \"explanation\": \"Indicates whether relay 0 is currently on or off\", \"type\": \"enum\", \"values\": [\"on\", \"off\"]}]}, \"timeout\": 10, \"timeout_unit\": \"sec\"}]', 1, '2025-05-11 17:19:53', '2025-05-12 08:28:45');

-- --------------------------------------------------------

--
-- Estrutura da tabela `alembic_version`
--

CREATE TABLE `alembic_version` (
  `version_num` varchar(32) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Extraindo dados da tabela `alembic_version`
--

INSERT INTO `alembic_version` (`version_num`) VALUES
('1713516d6639');

-- --------------------------------------------------------

--
-- Estrutura da tabela `cameras`
--

CREATE TABLE `cameras` (
  `id` int(11) NOT NULL,
  `device_id` int(11) DEFAULT NULL,
  `name` varchar(100) NOT NULL,
  `address` varchar(255) NOT NULL,
  `port` int(11) DEFAULT NULL,
  `username` varchar(50) DEFAULT NULL,
  `password` varchar(255) DEFAULT NULL,
  `manufacturer` varchar(100) DEFAULT NULL,
  `model` varchar(100) DEFAULT NULL,
  `firmware` varchar(50) DEFAULT NULL,
  `serial_number` varchar(100) DEFAULT NULL,
  `description` text DEFAULT NULL COMMENT 'Optional description of the camera',
  `notes` text DEFAULT NULL COMMENT 'Additional notes or comments',
  `default_stream_id` int(11) DEFAULT NULL,
  `snapshot_url` varchar(255) DEFAULT NULL COMMENT 'Direct full URL to fetch a snapshot image',
  `snapshot_prefix` varchar(255) DEFAULT NULL COMMENT 'Prefix for snapshot CGI endpoint',
  `snapshot_type` enum('manual','schedule','motion_event') NOT NULL COMMENT 'When snapshots are expected to be taken',
  `snapshot_interval_seconds` int(11) DEFAULT NULL COMMENT 'Interval in seconds for scheduled snapshots',
  `supports_motion_detection` tinyint(1) DEFAULT NULL,
  `supports_person_detection` tinyint(1) DEFAULT NULL,
  `supports_vehicle_detection` tinyint(1) DEFAULT NULL,
  `motion_detection_enabled` tinyint(1) DEFAULT NULL,
  `alert_via_email` tinyint(1) DEFAULT NULL,
  `alert_via_ftp` tinyint(1) DEFAULT NULL,
  `alert_via_http` tinyint(1) DEFAULT NULL,
  `status` enum('online','offline','error') NOT NULL,
  `last_heartbeat` datetime DEFAULT NULL,
  `last_error` varchar(255) DEFAULT NULL,
  `location` varchar(255) DEFAULT NULL COMMENT 'Physical location or area of the camera',
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Extraindo dados da tabela `cameras`
--

INSERT INTO `cameras` (`id`, `device_id`, `name`, `address`, `port`, `username`, `password`, `manufacturer`, `model`, `firmware`, `serial_number`, `description`, `notes`, `default_stream_id`, `snapshot_url`, `snapshot_prefix`, `snapshot_type`, `snapshot_interval_seconds`, `supports_motion_detection`, `supports_person_detection`, `supports_vehicle_detection`, `motion_detection_enabled`, `alert_via_email`, `alert_via_ftp`, `alert_via_http`, `status`, `last_heartbeat`, `last_error`, `location`, `created_at`, `updated_at`) VALUES
(1, 1, 'Factory Lens Cam 2', 'anr.microlumin.com', 554, 'admin', 'R0148636', 'Hilook', 'IPC‑B140H', '1.0', 'CAM1-0002', 'Entrance hallway camera', 'Mounted above door, covers main entry.', 24, '', '/cgi-bin/api.cgi', 'manual', 0, 0, 0, 0, 0, 0, 0, 0, 'online', '2025-05-12 08:54:46', NULL, 'Entrance', '2025-05-05 07:07:24', '2025-05-12 08:54:46'),
(2, 13, 'Camera 2', 'anr.microlumin.com', 554, 'admin', 'R0148636', NULL, 'Hilook IPC-B140H', NULL, '008122', NULL, NULL, 25, '', '/cgi-bin/api.cgi', 'manual', 0, 0, 0, 0, 0, 0, 0, 0, 'online', '2025-05-12 08:54:49', NULL, '', '2025-05-06 17:15:17', '2025-05-12 08:54:50'),
(3, 17, 'Câmara Armazem', '10.20.0.30', 5543, 'admin', 'L206C0F2', NULL, 'Hilook IPC-B140H', NULL, NULL, NULL, NULL, 23, '', '/cgi-bin/api.cgi', 'manual', 0, 0, 0, 0, 0, 0, 0, 0, 'offline', '2025-05-07 14:39:07', NULL, '', '2025-05-07 14:39:07', '2025-05-07 16:18:34');

-- --------------------------------------------------------

--
-- Estrutura da tabela `camera_streams`
--

CREATE TABLE `camera_streams` (
  `id` int(11) NOT NULL,
  `camera_id` int(11) NOT NULL,
  `stream_type` enum('main','sub','fluent','custom') NOT NULL COMMENT 'Type of stream channel',
  `url_prefix` varchar(255) DEFAULT NULL COMMENT 'Path prefix for stream URL, e.g. /h264Preview_01_',
  `stream_suffix` varchar(255) DEFAULT NULL COMMENT 'Suffix for stream path, e.g. main, sub',
  `full_url` varchar(255) DEFAULT NULL COMMENT 'Full RTSP/HTTP stream URL (overrides prefix+suffix)',
  `resolution_w` int(11) DEFAULT NULL,
  `resolution_h` int(11) DEFAULT NULL,
  `fps` int(11) DEFAULT NULL,
  `codec` varchar(50) DEFAULT NULL COMMENT 'e.g. H.264, H.265, MJPEG',
  `bitrate_kbps` int(11) DEFAULT NULL,
  `bitrate_type` varchar(50) DEFAULT NULL COMMENT 'CBR, VBR',
  `is_active` tinyint(1) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Extraindo dados da tabela `camera_streams`
--

INSERT INTO `camera_streams` (`id`, `camera_id`, `stream_type`, `url_prefix`, `stream_suffix`, `full_url`, `resolution_w`, `resolution_h`, `fps`, `codec`, `bitrate_kbps`, `bitrate_type`, `is_active`, `description`, `created_at`, `updated_at`) VALUES
(23, 3, 'main', '/cam/realmonitor?channel=1&subtype=1&unicast=true&proto=Onvif', NULL, NULL, 1920, 1080, 30, NULL, NULL, NULL, 1, 'Configured via UI', '2025-05-07 16:18:34', '2025-05-07 16:18:34'),
(24, 1, 'main', '/Streaming/Channels/101', NULL, NULL, 1920, 1080, 30, NULL, NULL, NULL, 1, 'Configured via UI', '2025-05-07 16:18:46', '2025-05-07 16:18:46'),
(25, 2, 'main', '/Streaming/Channels/301', NULL, NULL, 640, 360, 30, NULL, NULL, NULL, 1, 'Configured via UI', '2025-05-07 16:18:54', '2025-05-07 16:18:54');

-- --------------------------------------------------------

--
-- Estrutura da tabela `devices`
--

CREATE TABLE `devices` (
  `id` int(11) NOT NULL,
  `name` varchar(100) NOT NULL,
  `serial_number` varchar(100) DEFAULT NULL,
  `device_model_id` int(11) NOT NULL,
  `poll_interval` int(11) DEFAULT NULL COMMENT 'Polling frequency value',
  `poll_interval_unit` enum('ms','sec','min','hour','day') NOT NULL COMMENT 'Polling interval unit',
  `values` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'Runtime values such as state, ip, etc.' CHECK (json_valid(`values`)),
  `last_response_timestamp` datetime DEFAULT NULL,
  `mqtt_client_id` varchar(100) NOT NULL,
  `topic_prefix` varchar(200) NOT NULL COMMENT 'Root topic, e.g. ''shelly/1ABC23''',
  `parameters` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'Arbitrary JSON blob for extra settings' CHECK (json_valid(`parameters`)),
  `tags` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'List of tags for classification and filtering' CHECK (json_valid(`tags`)),
  `description` text DEFAULT NULL COMMENT 'Optional device description',
  `image` varchar(255) DEFAULT NULL COMMENT 'Optional image URL or path',
  `location` varchar(255) DEFAULT NULL COMMENT 'Logical or physical location of the device',
  `qr_code` varchar(255) DEFAULT NULL COMMENT 'QR code string or image URL',
  `enabled` tinyint(1) NOT NULL,
  `status` enum('online','offline','error') DEFAULT NULL,
  `last_seen` datetime DEFAULT NULL,
  `last_error` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Extraindo dados da tabela `devices`
--

INSERT INTO `devices` (`id`, `name`, `serial_number`, `device_model_id`, `poll_interval`, `poll_interval_unit`, `values`, `last_response_timestamp`, `mqtt_client_id`, `topic_prefix`, `parameters`, `tags`, `description`, `image`, `location`, `qr_code`, `enabled`, `status`, `last_seen`, `last_error`, `created_at`, `updated_at`) VALUES
(1, 'Factory Lens Cam 2', 'CAM1-0002', 4, 60, 'sec', '{}', '2025-05-05 07:07:24', 'factory-cam-002', 'factory/cameras/002', '{\"address\": \"anr.microlumin.com\", \"fps\": 30, \"motion_detection_enabled\": false, \"password\": \"R0148636\", \"port\": 554, \"resolution\": \"1920x1080\", \"snapshot_interval_seconds\": 0, \"snapshot_url\": \"\", \"stream_type\": \"primary\", \"stream_url_suffix\": \"/Streaming/Channels/101\", \"username\": \"admin\"}', '[\"factory\", \"camera\", \"entry\"]', 'Entrance hallway camera', '', 'Entrance', '', 1, 'online', '2025-05-12 08:54:46', NULL, '2025-05-05 07:07:24', '2025-05-12 08:54:46'),
(2, 'Local Storage', NULL, 5, 60, 'sec', NULL, '2025-05-05 08:55:41', 'local', 'storage', '{\"base_path\": \"local\", \"max_size_gb\": \"100\", \"retention_days\": 30}', NULL, '', '', '', '', 1, 'online', '2025-05-12 08:54:46', NULL, '2025-05-05 08:55:41', '2025-05-12 08:54:46'),
(5, 'FTP NAS', 'NAS-FTP', 6, 60, 'sec', NULL, '2025-05-05 11:10:44', 'ftpnas', 'storage', '{\"host\": \"10.20.1.5\", \"passive_mode\": true, \"password\": \"Eletrix+2024\", \"port\": 22, \"protocol\": \"sftp\", \"root_path\": \"/\", \"ssl\": false, \"username\": \"anr\"}', NULL, '', '', '', '', 0, 'online', '2025-05-11 18:36:43', NULL, '2025-05-05 11:10:44', '2025-05-11 18:37:09'),
(7, 'Machine Module', '0081F2', 9, 60, 'sec', '{\"relay\": {\"0\": {\"state\": \"off\", \"power\": \"0.00\", \"energy\": \"0\", \"command\": \"on\"}, \"1\": {\"state\": \"off\", \"power\": \"0.00\", \"energy\": \"0\", \"command\": \"on\"}}, \"input\": {\"0\": 1, \"1\": 0}, \"input_event\": {\"0\": {\"event\": \"\", \"event_cnt\": 0}, \"1\": {\"event\": \"\", \"event_cnt\": 0}}, \"temperature\": 45.98, \"temperature_f\": 114.76, \"overtemperature\": 0, \"temperature_status\": \"Normal\", \"voltage\": 0.15, \"online\": true, \"announce\": {\"id\": \"switch-0081F2\", \"model\": \"SHSW-25\", \"mac\": \"2462AB0081F2\", \"ip\": \"10.20.1.99\", \"new_fw\": false, \"fw_ver\": \"20230913-112234/v1.14.0-gcb84623\", \"mode\": \"relay\"}, \"info\": {\"wifi_sta\": {\"connected\": true, \"ssid\": \"microlumin-wifi\", \"ip\": \"10.20.1.99\", \"rssi\": -68}, \"cloud\": null}}', NULL, 'switch-0081F2', 'shellies', '{}', NULL, '', 'img/devices/iot/SHSW-25.png', '', '', 1, 'online', '2025-05-12 08:54:31', NULL, NULL, '2025-05-12 08:54:31'),
(12, 'Machine Module 2', '0081F3', 9, 60, 'sec', '{\"relay\": {\"0\": {\"state\": \"off\", \"power\": \"0.00\", \"energy\": \"0\", \"command\": \"on\"}, \"1\": {\"state\": \"off\", \"power\": \"0.00\", \"energy\": \"0\", \"command\": \"on\"}}, \"input\": {\"0\": 0, \"1\": 0}, \"input_event\": {\"0\": {\"event\": \"\", \"event_cnt\": 0}, \"1\": {\"event\": \"\", \"event_cnt\": 0}}, \"temperature\": 44.05, \"temperature_f\": 111.28, \"overtemperature\": 0, \"temperature_status\": \"Normal\", \"voltage\": 0.12, \"online\": false, \"announce\": {\"id\": \"switch-0081F2\", \"model\": \"SHSW-25\", \"mac\": \"2462AB0081F2\", \"ip\": \"10.20.1.99\", \"new_fw\": false, \"fw_ver\": \"20230913-112234/v1.14.0-gcb84623\", \"mode\": \"relay\"}, \"info\": {\"wifi_sta\": {\"connected\": true, \"ssid\": \"microlumin-wifi\", \"ip\": \"10.20.1.99\", \"rssi\": -68}, \"cloud\": null}}', NULL, 'switch-0081F3', 'shellies', '{}', NULL, '', 'img/devices/iot/SHSW-25.png', '', '', 1, 'online', '2025-05-12 08:54:46', NULL, NULL, '2025-05-12 08:54:46'),
(13, 'Camera 2', '008122', 4, 60, 'sec', NULL, '2025-05-06 17:15:17', '008122', 'cameras', '{\"address\": \"anr.microlumin.com\", \"fps\": 30, \"motion_detection_enabled\": false, \"password\": \"R0148636\", \"port\": 554, \"resolution\": \"640x360\", \"snapshot_interval_seconds\": 0, \"snapshot_url\": \"\", \"stream_type\": \"primary\", \"stream_url_suffix\": \"/Streaming/Channels/301\", \"username\": \"admin\"}', NULL, '', '', '', '', 1, 'online', '2025-05-12 08:54:49', NULL, '2025-05-06 17:15:17', '2025-05-12 08:54:50'),
(14, 'Main Action Agent', NULL, 10, 60, 'sec', NULL, '2025-05-07 11:14:48', 'action-agent', 'factory/action', NULL, NULL, NULL, NULL, NULL, NULL, 1, 'online', '2025-05-12 08:54:49', NULL, '2025-05-07 11:14:48', '2025-05-12 08:54:50'),
(15, 'Main Automation Agent', NULL, 11, 60, 'sec', NULL, '2025-05-07 11:14:48', 'automation-agent', 'factory/automation', NULL, NULL, NULL, NULL, NULL, NULL, 1, 'online', '2025-05-12 08:54:49', NULL, '2025-05-07 11:14:48', '2025-05-12 08:54:50'),
(16, 'Action Agent', NULL, 10, 60, 'sec', NULL, '2025-05-07 11:15:42', 'agent', 'actions/', '{}', NULL, '', '', '', '', 1, 'online', '2025-05-12 08:54:49', NULL, '2025-05-07 11:15:42', '2025-05-12 08:54:50'),
(17, 'Câmara Armazem', NULL, 4, 60, 'sec', NULL, '2025-05-07 14:39:07', 'L206C0F2', '/cameras/', '{\"address\": \"10.20.0.30\", \"fps\": 30, \"motion_detection_enabled\": false, \"password\": \"L206C0F2\", \"port\": 5543, \"resolution\": \"1920x1080\", \"snapshot_interval_seconds\": 0, \"snapshot_url\": \"\", \"stream_type\": \"primary\", \"stream_url_suffix\": \"/cam/realmonitor?channel=1&subtype=1&unicast=true&proto=Onvif\", \"username\": \"admin\"}', NULL, '', '', '', '', 0, 'offline', '2025-05-07 14:39:07', NULL, '2025-05-07 14:39:07', '2025-05-07 16:18:34');

-- --------------------------------------------------------

--
-- Estrutura da tabela `device_categories`
--

CREATE TABLE `device_categories` (
  `id` int(11) NOT NULL,
  `name` varchar(50) NOT NULL,
  `label` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Extraindo dados da tabela `device_categories`
--

INSERT INTO `device_categories` (`id`, `name`, `label`) VALUES
(1, 'camera', '📷 Camera'),
(2, 'messenger', '✉️ Messenger'),
(3, 'module', '📦 Module'),
(4, 'iot', '🔌 IoT Device'),
(5, 'logger', '📝 Logger'),
(6, 'storage', '💾 Storage Unit'),
(7, 'processor', '🧠 AI Processor');

-- --------------------------------------------------------

--
-- Estrutura da tabela `device_models`
--

CREATE TABLE `device_models` (
  `id` int(11) NOT NULL,
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL COMMENT 'Optional description of the device model',
  `serial_number` varchar(100) DEFAULT NULL COMMENT 'Serial number or hardware ID',
  `firmware` varchar(50) DEFAULT NULL COMMENT 'Firmware version',
  `manufacturer` varchar(100) DEFAULT NULL,
  `notes` text DEFAULT NULL,
  `category_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Extraindo dados da tabela `device_models`
--

INSERT INTO `device_models` (`id`, `name`, `description`, `serial_number`, `firmware`, `manufacturer`, `notes`, `category_id`) VALUES
(1, 'Shelly 1', NULL, NULL, NULL, NULL, 'Shelly 1 Wi-Fi relay', 4),
(2, 'Shelly 2', NULL, NULL, NULL, NULL, 'Shelly 2 dual relay', 4),
(3, 'Reolink 810A', NULL, NULL, NULL, NULL, 'Reolink 8 MP PoE camera', 1),
(4, 'Hilook IPC-B140H', NULL, NULL, NULL, NULL, 'Hilook 4 MP bullet camera', 1),
(5, 'Local storage', 'Local storage for storing files', NULL, NULL, NULL, NULL, 6),
(6, 'FTP / SFTP storage', 'FTP / SFTP storage for storing files', NULL, NULL, NULL, NULL, 6),
(7, 'Network share', 'Network share for storing files', NULL, NULL, NULL, NULL, 6),
(8, 'Cloud storage', 'Cloud storage for storing files', NULL, NULL, NULL, NULL, 6),
(9, 'Shelly 2.5 MQTT', 'Shelly 2.5 via MQTT', NULL, NULL, NULL, NULL, 4),
(10, 'Action Agent', NULL, NULL, NULL, NULL, NULL, 7),
(11, 'Automation Agent', NULL, NULL, NULL, NULL, NULL, 7);

-- --------------------------------------------------------

--
-- Estrutura da tabela `device_schemas`
--

CREATE TABLE `device_schemas` (
  `id` int(11) NOT NULL,
  `model_id` int(11) NOT NULL,
  `kind` enum('config','topic','function') NOT NULL,
  `schema` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`schema`)),
  `version` varchar(20) DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Extraindo dados da tabela `device_schemas`
--

INSERT INTO `device_schemas` (`id`, `model_id`, `kind`, `schema`, `version`, `updated_at`) VALUES
(1, 9, 'topic', '{\"topics\": {\"input/0\": {\"label\": \"Input 0\", \"tooltip\": \"Digital input channel 0 state\", \"hint\": \"True when the input is active (e.g. button pressed)\", \"explanation\": \"Reports the boolean state of input 0; 1=pressed, 0=released\", \"type\": \"bool\", \"true\": 1, \"false\": 0, \"poll_interval\": 0, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"\", \"poll_payload\": \"\"}, \"input/1\": {\"label\": \"Input 1\", \"tooltip\": \"Digital input channel 1 state\", \"hint\": \"True when the input is active\", \"explanation\": \"Reports the boolean state of input 1; 1=pressed, 0=released\", \"type\": \"bool\", \"true\": 1, \"false\": 0, \"poll_interval\": 0, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"\", \"poll_payload\": \"\"}, \"input_event/0\": {\"label\": \"Button 0 Event\", \"tooltip\": \"Type of event on button 0\", \"hint\": \"Select short or long press\", \"explanation\": \"Emitted when button 0 is pressed: \'S\'=short, \'L\'=long\", \"type\": \"enum\", \"values\": [\"S\", \"L\"], \"display\": {\"S\": \"Short Press\", \"L\": \"Long Press\"}, \"poll_interval\": 0, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"\", \"poll_payload\": \"\"}, \"input_event/1\": {\"label\": \"Button 1 Event\", \"tooltip\": \"Type of event on button 1\", \"hint\": \"Select short or long press\", \"explanation\": \"Emitted when button 1 is pressed: \'S\'=short, \'L\'=long, \'\'=none\", \"type\": \"enum\", \"values\": [\"\", \"S\", \"L\"], \"display\": {\"\": \"None\", \"S\": \"Short Press\", \"L\": \"Long Press\"}, \"poll_interval\": 0, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"\", \"poll_payload\": \"\"}, \"relay/0\": {\"label\": \"Relay 0 State\", \"tooltip\": \"Current on/off state of relay 0\", \"hint\": \"Use Evaluate to check on/off\", \"explanation\": \"Indicates whether relay 0 is currently on or off\", \"type\": \"enum\", \"values\": [\"on\", \"off\"], \"poll_interval\": 0, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"\", \"poll_payload\": \"\"}, \"relay/0/power\": {\"label\": \"Relay 0 Power\", \"tooltip\": \"Instantaneous power draw of relay 0\", \"hint\": \"Enter a watt threshold\", \"explanation\": \"Reports power consumption in watts for relay 0\", \"type\": \"number\", \"units\": \"W\", \"range\": [0, null], \"comparators\": [\"<\", \"<=\", \"==\", \"!=\", \" >=\", \">\"], \"poll_interval\": 60, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"relay/0/power\", \"poll_payload\": \"\"}, \"relay/0/energy\": {\"label\": \"Relay 0 Energy\", \"tooltip\": \"Cumulative energy usage of relay 0\", \"hint\": \"Enter watt\\u2010hour limit\", \"explanation\": \"Total energy consumed by relay 0 in Wh\", \"type\": \"number\", \"units\": \"Wh\", \"poll_interval\": 60, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"relay/0/energy\", \"poll_payload\": \"\"}, \"relay/1\": {\"label\": \"Relay 1 State\", \"tooltip\": \"Current on/off state of relay 1\", \"hint\": \"Use Evaluate to check on/off\", \"explanation\": \"Indicates whether relay 1 is currently on or off\", \"type\": \"enum\", \"values\": [\"on\", \"off\"], \"poll_interval\": 0, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"\", \"poll_payload\": \"\"}, \"relay/1/power\": {\"label\": \"Relay 1 Power\", \"tooltip\": \"Instantaneous power draw of relay 1\", \"hint\": \"Enter a watt threshold\", \"explanation\": \"Reports power consumption in watts for relay 1\", \"type\": \"number\", \"units\": \"W\", \"range\": [0, null], \"comparators\": [\"<\", \"<=\", \"==\", \"!=\", \" >=\", \">\"], \"poll_interval\": 60, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"relay/1/power\", \"poll_payload\": \"\"}, \"relay/1/energy\": {\"label\": \"Relay 1 Energy\", \"tooltip\": \"Cumulative energy usage of relay 1\", \"hint\": \"Enter watt\\u2010hour limit\", \"explanation\": \"Total energy consumed by relay 1 in Wh\", \"type\": \"number\", \"units\": \"Wh\", \"poll_interval\": 60, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"relay/1/energy\", \"poll_payload\": \"\"}, \"temperature\": {\"label\": \"Temperature (\\u00b0C)\", \"tooltip\": \"Device internal temperature\", \"hint\": \"Enter \\u00b0C threshold\", \"explanation\": \"Shows the current temperature inside the device in Celsius\", \"type\": \"number\", \"units\": \"\\u00b0C\", \"range\": [-50, 150], \"comparators\": [\"<\", \"<=\", \"==\", \"!=\", \" >=\", \">\"], \"poll_interval\": 60, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"temperature\", \"poll_payload\": \"\"}, \"temperature_f\": {\"label\": \"Temperature (\\u00b0F)\", \"tooltip\": \"Device internal temperature\", \"hint\": \"Enter \\u00b0F threshold\", \"explanation\": \"Shows the current temperature inside the device in Fahrenheit\", \"type\": \"number\", \"units\": \"\\u00b0F\", \"range\": [-58, 302], \"poll_interval\": 60, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"temperature_f\", \"poll_payload\": \"\"}, \"temperature_status\": {\"label\": \"Temperature Status\", \"tooltip\": \"Overtemperature indicator\", \"hint\": \"Check for \'Overheated\'\", \"explanation\": \"Indicates if the device temperature is normal or overheated\", \"type\": \"enum\", \"values\": [\"Normal\", \"Overheated\"], \"poll_interval\": 60, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"temperature_status\", \"poll_payload\": \"\"}, \"overtemperature\": {\"label\": \"Overtemperature\", \"tooltip\": \"Boolean overtemperature flag\", \"hint\": \"True if over temperature\", \"explanation\": \"Reports a boolean flag when device temperature exceeds safe limits\", \"type\": \"bool\", \"true\": 1, \"false\": 0, \"poll_interval\": 60, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"overtemperature\", \"poll_payload\": \"\"}, \"voltage\": {\"label\": \"Voltage\", \"tooltip\": \"Supply voltage reading\", \"hint\": \"Enter V threshold\", \"explanation\": \"Reports the device\\u2019s supply voltage in volts\", \"type\": \"number\", \"units\": \"V\", \"poll_interval\": 60, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"voltage\", \"poll_payload\": \"\"}, \"online\": {\"label\": \"Device Online\", \"tooltip\": \"Connectivity status\", \"hint\": \"True if device is online\", \"explanation\": \"Indicates whether the device is currently reachable via MQTT\", \"type\": \"bool\", \"poll_interval\": 30, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"online\", \"poll_payload\": \"\"}, \"info/wifi_sta/rssi\": {\"label\": \"WiFi RSSI\", \"tooltip\": \"WiFi signal strength\", \"hint\": \"Enter minimum RSSI (dBm)\", \"explanation\": \"Shows the received signal strength indicator of the WiFi connection\", \"type\": \"number\", \"units\": \"dBm\", \"poll_interval\": 60, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"info/wifi_sta/rssi\", \"poll_payload\": \"\"}}, \"command_topics\": {\"relay/0/command\": {\"label\": \"Relay 0 Command\", \"tooltip\": \"Turn relay 0 on or off\", \"hint\": \"Choose \'on\' to energize, \'off\' to de-energize\", \"explanation\": \"Sends a command to switch relay channel 0\", \"type\": \"enum\", \"values\": [\"on\", \"off\"], \"timeout\": 10, \"timeout_unit\": \"sec\", \"result_topic\": \"relay/0\", \"result_payload\": {\"options\": [{\"label\": \"Relay 0 State\", \"tooltip\": \"Current on/off state of relay 0\", \"hint\": \"Use Evaluate to check on/off\", \"explanation\": \"Indicates whether relay 0 is currently on or off\", \"type\": \"enum\", \"values\": [\"on\", \"off\"]}]}}, \"relay/1/command\": {\"label\": \"Relay 1 Command\", \"tooltip\": \"Turn relay 1 on or off\", \"hint\": \"Choose \'on\' or \'off\'\", \"explanation\": \"Sends a command to switch relay channel 1\", \"type\": \"enum\", \"values\": [\"on\", \"off\"], \"timeout\": 10, \"timeout_unit\": \"sec\", \"result_topic\": \"relay/1\", \"result_payload\": {\"options\": [{\"label\": \"Relay 1 State\", \"tooltip\": \"Current on/off state of relay 1\", \"hint\": \"Use Evaluate to check on/off\", \"explanation\": \"Indicates whether relay 1 is currently on or off\", \"type\": \"enum\", \"values\": [\"on\", \"off\"]}]}}}}', '1.0.0', '2025-05-10 09:55:13'),
(2, 4, 'topic', '{\"topics\": {\"snapshot\": {\"label\": \"Snapshot\", \"tooltip\": \"Camera snapshot event\", \"hint\": \"The file format is indicated by its extension\", \"explanation\": \"Publishes a binary snapshot; use Evaluate to check its extension\", \"type\": \"file\", \"values\": [\"jpg\", \"pdf\"], \"poll_interval\": 0, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"\", \"poll_payload\": \"\"}}, \"command_topics\": {\"snapshot/exe\": {\"label\": \"Take Snapshot\", \"tooltip\": \"Request a new snapshot\", \"hint\": \"Choose \'jpg\' or \'pdf\' output\", \"explanation\": \"Sends a command to capture an image; publishes file on \'snapshot\'\", \"type\": \"enum\", \"values\": [\"jpg\", \"pdf\"], \"timeout\": 30, \"timeout_unit\": \"sec\", \"result_topic\": \"snapshot\", \"result_payload\": {\"options\": [{\"label\": \"Snapshot Format\", \"tooltip\": \"Format of the returned snapshot\", \"hint\": \"Indicates whether the snapshot was jpg or pdf\", \"type\": \"file\", \"values\": [\"jpg\", \"pdf\"]}]}}}}', '1.0.0', '2025-05-11 09:56:24'),
(3, 5, 'topic', '{\"topics\": {\"file/created\": {\"label\": \"File Saved\", \"tooltip\": \"Indicates a new file was saved\", \"hint\": \"Relative path under the storage unit\", \"explanation\": \"Emitted after a successful save; payload is file path\", \"type\": \"enum\", \"values\": [\"success\", \"error\"], \"display\": {\"success\": \"\\u2705 Success\", \"error\": \"\\u274c Error\"}, \"poll_interval\": 0, \"poll_interval_unit\": \"sec\", \"poll_topic\": \"\", \"poll_payload\": \"\"}}, \"command_topics\": {\"file/image/create\": {\"label\": \"Save File\", \"tooltip\": \"Save a file to this storage unit\", \"hint\": \"Payload must include a base64 file and extension\", \"explanation\": \"Receives `{ext: \'jpg\'|\'pdf\', file: \'...\'}` and stores it on disk\", \"type\": \"file\", \"values\": [\"jpg\", \"pdf\"], \"timeout\": 30, \"timeout_unit\": \"sec\", \"result_topic\": \"file/created\", \"result_payload\": {\"options\": [{\"label\": \"Outcome\", \"tooltip\": \"Whether the save succeeded or failed\", \"hint\": \"Use this to route success vs error\", \"type\": \"enum\", \"values\": [\"success\", \"error\"], \"display\": {\"success\": \"\\u2705 Success\", \"error\": \"\\u274c Error\"}}], \"details\": {\"label\": \"Stored File Path\", \"tooltip\": \"Relative path under the storage unit\", \"hint\": \"Available after a successful save\", \"type\": \"string\"}}}}}', '1.0.0', '2025-05-11 17:08:10'),
(4, 5, 'config', '{\"type\": \"object\", \"title\": \"Local storage configuration\", \"properties\": {\"base_path\": {\"type\": \"string\", \"title\": \"Base directory\", \"minLength\": 1}, \"max_size_gb\": {\"type\": \"number\", \"title\": \"Max size (GB)\", \"default\": 100}, \"retention_days\": {\"type\": \"integer\", \"title\": \"Retention (days)\", \"default\": 30}}, \"required\": [\"base_path\"]}', '1.0.0', '2025-05-11 14:55:35'),
(5, 6, 'config', '{\"type\": \"object\", \"title\": \"FTP / SFTP storage configuration\", \"properties\": {\"protocol\": {\"type\": \"string\", \"enum\": [\"ftp\", \"sftp\"], \"default\": \"ftp\"}, \"host\": {\"type\": \"string\", \"title\": \"Host\", \"minLength\": 1}, \"port\": {\"type\": \"integer\", \"title\": \"Port\", \"default\": 21}, \"username\": {\"type\": \"string\"}, \"password\": {\"type\": \"string\", \"format\": \"password\"}, \"root_path\": {\"type\": \"string\", \"title\": \"Root path\", \"default\": \"/\"}, \"passive_mode\": {\"type\": \"boolean\", \"title\": \"Passive mode\", \"default\": true}, \"ssl\": {\"type\": \"boolean\", \"title\": \"Use SSL/TLS\", \"default\": false}}, \"required\": [\"protocol\", \"host\"]}', '1.0.0', '2025-05-11 14:55:35'),
(6, 7, 'config', '{\"type\": \"object\", \"title\": \"Network share (SMB/NFS) configuration\", \"properties\": {\"share_type\": {\"type\": \"string\", \"enum\": [\"smb\", \"nfs\"], \"default\": \"smb\"}, \"path\": {\"type\": \"string\", \"title\": \"UNC / NFS path\", \"minLength\": 1}, \"username\": {\"type\": \"string\"}, \"password\": {\"type\": \"string\", \"format\": \"password\"}, \"mount_options\": {\"type\": \"string\", \"title\": \"Mount options\"}}, \"required\": [\"share_type\", \"path\"]}', '1.0.0', '2025-05-11 14:55:35'),
(7, 8, 'config', '{\"type\": \"object\", \"title\": \"Cloud storage configuration\", \"properties\": {\"provider\": {\"type\": \"string\", \"enum\": [\"gdrive\", \"dropbox\", \"onedrive\", \"mega\"], \"default\": \"gdrive\"}, \"credentials\": {\"type\": \"string\", \"title\": \"Credentials JSON / token\", \"format\": \"textarea\"}, \"root_folder\": {\"type\": \"string\", \"title\": \"Root folder\", \"default\": \"\"}, \"cache_ttl\": {\"type\": \"integer\", \"title\": \"Cache TTL (seconds)\", \"default\": 300}}, \"required\": [\"provider\", \"credentials\"]}', '1.0.0', '2025-05-11 14:55:35');

-- --------------------------------------------------------

--
-- Estrutura da tabela `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `username` varchar(80) NOT NULL,
  `email` varchar(120) NOT NULL,
  `name` varchar(80) NOT NULL,
  `surname` varchar(80) NOT NULL,
  `avatar_image` varchar(255) DEFAULT NULL,
  `password` varchar(255) NOT NULL,
  `role` varchar(20) NOT NULL,
  `language` varchar(10) NOT NULL,
  `recovery_token` varchar(255) DEFAULT NULL,
  `pin` varchar(10) DEFAULT NULL,
  `active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Índices para tabelas despejadas
--

--
-- Índices para tabela `actions`
--
ALTER TABLE `actions`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `name` (`name`);

--
-- Índices para tabela `alembic_version`
--
ALTER TABLE `alembic_version`
  ADD PRIMARY KEY (`version_num`);

--
-- Índices para tabela `cameras`
--
ALTER TABLE `cameras`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `name` (`name`),
  ADD UNIQUE KEY `serial_number` (`serial_number`),
  ADD KEY `default_stream_id` (`default_stream_id`),
  ADD KEY `device_id` (`device_id`);

--
-- Índices para tabela `camera_streams`
--
ALTER TABLE `camera_streams`
  ADD PRIMARY KEY (`id`),
  ADD KEY `camera_id` (`camera_id`);

--
-- Índices para tabela `devices`
--
ALTER TABLE `devices`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `name` (`name`),
  ADD UNIQUE KEY `mqtt_client_id` (`mqtt_client_id`),
  ADD UNIQUE KEY `serial_number` (`serial_number`),
  ADD KEY `device_model_id` (`device_model_id`);

--
-- Índices para tabela `device_categories`
--
ALTER TABLE `device_categories`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `name` (`name`);

--
-- Índices para tabela `device_models`
--
ALTER TABLE `device_models`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `name` (`name`),
  ADD UNIQUE KEY `serial_number` (`serial_number`),
  ADD KEY `category_id` (`category_id`);

--
-- Índices para tabela `device_schemas`
--
ALTER TABLE `device_schemas`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_model_kind` (`model_id`,`kind`);

--
-- Índices para tabela `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`),
  ADD UNIQUE KEY `email` (`email`);

--
-- AUTO_INCREMENT de tabelas despejadas
--

--
-- AUTO_INCREMENT de tabela `actions`
--
ALTER TABLE `actions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=17;

--
-- AUTO_INCREMENT de tabela `cameras`
--
ALTER TABLE `cameras`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT de tabela `camera_streams`
--
ALTER TABLE `camera_streams`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=26;

--
-- AUTO_INCREMENT de tabela `devices`
--
ALTER TABLE `devices`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=19;

--
-- AUTO_INCREMENT de tabela `device_categories`
--
ALTER TABLE `device_categories`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=8;

--
-- AUTO_INCREMENT de tabela `device_models`
--
ALTER TABLE `device_models`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=12;

--
-- AUTO_INCREMENT de tabela `device_schemas`
--
ALTER TABLE `device_schemas`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=8;

--
-- AUTO_INCREMENT de tabela `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- Restrições para despejos de tabelas
--

--
-- Limitadores para a tabela `cameras`
--
ALTER TABLE `cameras`
  ADD CONSTRAINT `cameras_ibfk_1` FOREIGN KEY (`default_stream_id`) REFERENCES `camera_streams` (`id`),
  ADD CONSTRAINT `cameras_ibfk_2` FOREIGN KEY (`device_id`) REFERENCES `devices` (`id`);

--
-- Limitadores para a tabela `camera_streams`
--
ALTER TABLE `camera_streams`
  ADD CONSTRAINT `camera_streams_ibfk_1` FOREIGN KEY (`camera_id`) REFERENCES `cameras` (`id`);

--
-- Limitadores para a tabela `devices`
--
ALTER TABLE `devices`
  ADD CONSTRAINT `devices_ibfk_1` FOREIGN KEY (`device_model_id`) REFERENCES `device_models` (`id`);

--
-- Limitadores para a tabela `device_models`
--
ALTER TABLE `device_models`
  ADD CONSTRAINT `device_models_ibfk_1` FOREIGN KEY (`category_id`) REFERENCES `device_categories` (`id`);

--
-- Limitadores para a tabela `device_schemas`
--
ALTER TABLE `device_schemas`
  ADD CONSTRAINT `device_schemas_ibfk_1` FOREIGN KEY (`model_id`) REFERENCES `device_models` (`id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
