-- Park Patrol database
-- Import in phpMyAdmin (Import tab), or let the server create it on startup.

CREATE DATABASE IF NOT EXISTS parkpatrol CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE parkpatrol;

-- ---------------------------------------------------------------------------
-- Admin accounts (the Google account each admin signed in with)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admins (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  google_sub    VARCHAR(64)  NOT NULL UNIQUE COMMENT 'Permanent Google account ID',
  email         VARCHAR(255) NOT NULL UNIQUE,
  name          VARCHAR(255) NULL,
  given_name    VARCHAR(128) NULL,
  family_name   VARCHAR(128) NULL,
  picture_url   VARCHAR(512) NULL,
  hosted_domain VARCHAR(255) NULL COMMENT 'Google Workspace domain, e.g. dlsl.edu.ph',
  locale        VARCHAR(16)  NULL,
  login_count   INT UNSIGNED NOT NULL DEFAULT 0,
  first_login   DATETIME     NOT NULL,
  last_login    DATETIME     NOT NULL
) ENGINE=InnoDB;

-- Every sign-in attempt, sign-out, and rejected Google account
CREATE TABLE IF NOT EXISTS auth_events (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  admin_id    INT UNSIGNED NULL,
  event       ENUM('login', 'logout', 'denied', 'unverified', 'error') NOT NULL,
  email       VARCHAR(255) NULL,
  google_sub  VARCHAR(64)  NULL,
  name        VARCHAR(255) NULL,
  ip_address  VARCHAR(45)  NULL,
  user_agent  VARCHAR(255) NULL,
  detail      VARCHAR(255) NULL,
  created_at  DATETIME(3)  NOT NULL,
  INDEX idx_auth_created (created_at),
  INDEX idx_auth_email (email),
  CONSTRAINT fk_auth_admin FOREIGN KEY (admin_id) REFERENCES admins (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Parking spots and their history
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS spots (
  id          VARCHAR(4)  PRIMARY KEY COMMENT 'A1 to A18',
  lot         VARCHAR(16) NOT NULL DEFAULT 'A',
  side        ENUM('top', 'right', 'bottom', 'left') NOT NULL,
  position    TINYINT UNSIGNED NOT NULL,
  status      ENUM('VACANT', 'OCCUPIED', 'VIOLATION_DOUBLE_PARKED') NOT NULL DEFAULT 'VACANT',
  status_since DATETIME(3) NOT NULL
) ENGINE=InnoDB;

-- Every status change reported by the tracker
CREATE TABLE IF NOT EXISTS spot_events (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  spot_id     VARCHAR(4) NOT NULL,
  from_status ENUM('VACANT', 'OCCUPIED', 'VIOLATION_DOUBLE_PARKED') NOT NULL,
  to_status   ENUM('VACANT', 'OCCUPIED', 'VIOLATION_DOUBLE_PARKED') NOT NULL,
  duration_seconds INT UNSIGNED NULL COMMENT 'How long the previous status lasted',
  created_at  DATETIME(3) NOT NULL,
  INDEX idx_events_spot (spot_id, created_at),
  INDEX idx_events_created (created_at),
  CONSTRAINT fk_events_spot FOREIGN KEY (spot_id) REFERENCES spots (id)
) ENGINE=InnoDB;

-- Lot-wide counts every few minutes (busiest hours, daily reports)
CREATE TABLE IF NOT EXISTS occupancy_snapshots (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  vacant      TINYINT UNSIGNED NOT NULL,
  occupied    TINYINT UNSIGNED NOT NULL,
  violations  TINYINT UNSIGNED NOT NULL,
  total       TINYINT UNSIGNED NOT NULL,
  occupancy_pct DECIMAL(5, 2) NOT NULL,
  tracker_online BOOLEAN NOT NULL,
  created_at  DATETIME NOT NULL,
  INDEX idx_snapshots_created (created_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Violations (double parking) and security alerts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS violations (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  spots_label VARCHAR(32) NOT NULL COMMENT 'e.g. A3+A4 when a car blocks several spots',
  started_at  DATETIME(3) NOT NULL,
  cleared_at  DATETIME(3) NULL,
  duration_seconds INT UNSIGNED NULL,
  snapshot    MEDIUMBLOB  NULL COMMENT 'Camera frame (JPEG) when the violation started',
  INDEX idx_violations_started (started_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS violation_spots (
  violation_id INT UNSIGNED NOT NULL,
  spot_id      VARCHAR(4)   NOT NULL,
  PRIMARY KEY (violation_id, spot_id),
  CONSTRAINT fk_vs_violation FOREIGN KEY (violation_id) REFERENCES violations (id) ON DELETE CASCADE,
  CONSTRAINT fk_vs_spot FOREIGN KEY (spot_id) REFERENCES spots (id)
) ENGINE=InnoDB;

-- Every Telegram message sent to the security group
CREATE TABLE IF NOT EXISTS security_alerts (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  violation_id INT UNSIGNED NULL,
  kind         ENUM('detected', 'cleared', 'manual') NOT NULL,
  sent_by      INT UNSIGNED NULL COMMENT 'Admin who pressed Alert (NULL = automatic)',
  success      BOOLEAN      NOT NULL,
  error        VARCHAR(255) NULL,
  created_at   DATETIME(3)  NOT NULL,
  INDEX idx_alerts_created (created_at),
  CONSTRAINT fk_alerts_violation FOREIGN KEY (violation_id) REFERENCES violations (id) ON DELETE SET NULL,
  CONSTRAINT fk_alerts_admin FOREIGN KEY (sent_by) REFERENCES admins (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Public Telegram subscribers (chat ID only: no name, email, or phone)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS telegram_subscribers (
  chat_id         BIGINT      PRIMARY KEY,
  active          BOOLEAN     NOT NULL DEFAULT TRUE,
  subscribed_at   DATETIME    NOT NULL,
  unsubscribed_at DATETIME    NULL,
  unsubscribe_reason ENUM('stop', 'blocked') NULL,
  last_notified_at DATETIME   NULL,
  notifications_sent INT UNSIGNED NOT NULL DEFAULT 0
) ENGINE=InnoDB;

-- Each "a spot just opened" broadcast
CREATE TABLE IF NOT EXISTS availability_broadcasts (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  spot_id     VARCHAR(4)  NOT NULL,
  recipients  INT UNSIGNED NOT NULL,
  delivered   INT UNSIGNED NOT NULL,
  created_at  DATETIME(3) NOT NULL,
  INDEX idx_broadcasts_created (created_at),
  CONSTRAINT fk_broadcasts_spot FOREIGN KEY (spot_id) REFERENCES spots (id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- System health (server restarts, tracker going offline / back online)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_events (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  event       ENUM('server_started', 'tracker_online', 'tracker_offline') NOT NULL,
  detail      VARCHAR(255) NULL,
  created_at  DATETIME(3) NOT NULL,
  INDEX idx_system_created (created_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Lot A layout (matches static/lot.js)
-- ---------------------------------------------------------------------------
INSERT IGNORE INTO spots (id, side, position, status_since) VALUES
  ('A1', 'top', 1, NOW(3)), ('A2', 'top', 2, NOW(3)), ('A3', 'top', 3, NOW(3)),
  ('A4', 'top', 4, NOW(3)), ('A5', 'top', 5, NOW(3)),
  ('A6', 'right', 1, NOW(3)), ('A7', 'right', 2, NOW(3)), ('A8', 'right', 3, NOW(3)), ('A9', 'right', 4, NOW(3)),
  ('A10', 'bottom', 1, NOW(3)), ('A11', 'bottom', 2, NOW(3)), ('A12', 'bottom', 3, NOW(3)),
  ('A13', 'bottom', 4, NOW(3)), ('A14', 'bottom', 5, NOW(3)),
  ('A15', 'left', 1, NOW(3)), ('A16', 'left', 2, NOW(3)), ('A17', 'left', 3, NOW(3)), ('A18', 'left', 4, NOW(3));
