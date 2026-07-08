CREATE TABLE `user` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `username` VARCHAR(64) NOT NULL,
  `display_name` VARCHAR(64) NULL,
  `role` VARCHAR(32) NOT NULL,
  `class_id` VARCHAR(64) NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'active',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `chk_user_role` CHECK (`role` IN ('student', 'teacher', 'admin')),
  CONSTRAINT `chk_user_status` CHECK (`status` IN ('active', 'disabled')),
  UNIQUE KEY `uk_user_username` (`username`),
  KEY `idx_user_role_class` (`role`, `class_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `course` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `course_code` VARCHAR(64) NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `description` TEXT NULL,
  `term` VARCHAR(64) NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'active',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `chk_course_status` CHECK (`status` IN ('active', 'archived')),
  UNIQUE KEY `uk_course_code` (`course_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `knowledge_point` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `course_id` BIGINT NOT NULL,
  `parent_id` BIGINT NULL,
  `code` VARCHAR(64) NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `description` TEXT NULL,
  `material_path` VARCHAR(255) NULL,
  `difficulty_level` VARCHAR(32) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_knowledge_point_course` FOREIGN KEY (`course_id`) REFERENCES `course` (`id`),
  CONSTRAINT `fk_knowledge_point_parent` FOREIGN KEY (`parent_id`) REFERENCES `knowledge_point` (`id`),
  CONSTRAINT `chk_knowledge_point_difficulty` CHECK (`difficulty_level` IS NULL OR `difficulty_level` IN ('basic', 'medium', 'advanced')),
  UNIQUE KEY `uk_knowledge_point_course_code` (`course_id`, `code`),
  KEY `idx_knowledge_point_parent` (`parent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `question` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `course_id` BIGINT NOT NULL,
  `knowledge_point_id` BIGINT NULL,
  `question_type` VARCHAR(64) NOT NULL DEFAULT 'concept',
  `question_text` TEXT NOT NULL,
  `reference_answer` TEXT NULL,
  `difficulty` VARCHAR(32) NULL,
  `source` VARCHAR(128) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_question_course` FOREIGN KEY (`course_id`) REFERENCES `course` (`id`),
  CONSTRAINT `fk_question_knowledge_point` FOREIGN KEY (`knowledge_point_id`) REFERENCES `knowledge_point` (`id`),
  CONSTRAINT `chk_question_type` CHECK (`question_type` IN ('concept', 'calculation', 'analysis', 'timing')),
  CONSTRAINT `chk_question_difficulty` CHECK (`difficulty` IS NULL OR `difficulty` IN ('easy', 'medium', 'hard')),
  KEY `idx_question_course_kp` (`course_id`, `knowledge_point_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `qa_record` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `course_id` BIGINT NOT NULL,
  `knowledge_point_id` BIGINT NULL,
  `question` TEXT NOT NULL,
  `answer` TEXT NOT NULL,
  `agent_payload` JSON NULL,
  `confidence` VARCHAR(32) NULL,
  `need_more_information` BOOLEAN NOT NULL DEFAULT FALSE,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_qa_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_qa_course` FOREIGN KEY (`course_id`) REFERENCES `course` (`id`),
  CONSTRAINT `fk_qa_knowledge_point` FOREIGN KEY (`knowledge_point_id`) REFERENCES `knowledge_point` (`id`),
  CONSTRAINT `chk_qa_confidence` CHECK (`confidence` IS NULL OR `confidence` IN ('high', 'medium', 'low')),
  KEY `idx_qa_user_course_time` (`user_id`, `course_id`, `created_at`),
  KEY `idx_qa_course_kp_time` (`course_id`, `knowledge_point_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `wrong_record` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `question_id` BIGINT NULL,
  `course_id` BIGINT NOT NULL,
  `knowledge_point_id` BIGINT NULL,
  `question_text` TEXT NOT NULL,
  `student_answer` TEXT NOT NULL,
  `reference_answer` TEXT NULL,
  `diagnosis` TEXT NOT NULL,
  `diagnosis_payload` JSON NULL,
  `error_type` VARCHAR(128) NULL,
  `priority` VARCHAR(32) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_wrong_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_wrong_question` FOREIGN KEY (`question_id`) REFERENCES `question` (`id`),
  CONSTRAINT `fk_wrong_course` FOREIGN KEY (`course_id`) REFERENCES `course` (`id`),
  CONSTRAINT `fk_wrong_knowledge_point` FOREIGN KEY (`knowledge_point_id`) REFERENCES `knowledge_point` (`id`),
  CONSTRAINT `chk_wrong_priority` CHECK (`priority` IS NULL OR `priority` IN ('high', 'medium', 'low')),
  KEY `idx_wrong_user_course_time` (`user_id`, `course_id`, `created_at`),
  KEY `idx_wrong_course_kp_time` (`course_id`, `knowledge_point_id`, `created_at`),
  KEY `idx_wrong_error_type` (`error_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `learning_profile` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `course_id` BIGINT NOT NULL,
  `weak_points_json` JSON NULL,
  `study_plan_json` JSON NULL,
  `mastery_score` DECIMAL(5,2) NULL,
  `last_generated_at` DATETIME NULL,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_profile_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_profile_course` FOREIGN KEY (`course_id`) REFERENCES `course` (`id`),
  CONSTRAINT `chk_profile_mastery_score` CHECK (`mastery_score` IS NULL OR (`mastery_score` >= 0 AND `mastery_score` <= 100)),
  UNIQUE KEY `uk_profile_user_course` (`user_id`, `course_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `teaching_statistics` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `course_id` BIGINT NOT NULL,
  `class_id` VARCHAR(64) NULL,
  `stat_type` VARCHAR(64) NOT NULL,
  `stat_data` JSON NOT NULL,
  `stat_date` DATE NOT NULL,
  `generated_by` VARCHAR(64) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_teaching_statistics_course` FOREIGN KEY (`course_id`) REFERENCES `course` (`id`),
  CONSTRAINT `chk_teaching_statistics_type` CHECK (`stat_type` IN ('high_question', 'error_type', 'weak_point', 'activity', 'teaching_suggestion')),
  UNIQUE KEY `uk_stats_course_class_type_date` (`course_id`, `class_id`, `stat_type`, `stat_date`),
  KEY `idx_stats_course_type_date` (`course_id`, `stat_type`, `stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
