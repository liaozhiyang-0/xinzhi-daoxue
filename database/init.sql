CREATE TABLE `user` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `username` VARCHAR(64) NOT NULL,
  `role` VARCHAR(32) NOT NULL,
  `class_id` VARCHAR(64) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `course` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `course_code` VARCHAR(64) NOT NULL UNIQUE,
  `name` VARCHAR(128) NOT NULL,
  `description` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `knowledge_point` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `course_id` BIGINT NOT NULL,
  `code` VARCHAR(64) NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `description` TEXT NULL,
  CONSTRAINT `fk_knowledge_point_course` FOREIGN KEY (`course_id`) REFERENCES `course` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `question` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `course_id` BIGINT NOT NULL,
  `knowledge_point_id` BIGINT NULL,
  `question_text` TEXT NOT NULL,
  `reference_answer` TEXT NULL,
  `difficulty` VARCHAR(32) NULL,
  CONSTRAINT `fk_question_course` FOREIGN KEY (`course_id`) REFERENCES `course` (`id`),
  CONSTRAINT `fk_question_knowledge_point` FOREIGN KEY (`knowledge_point_id`) REFERENCES `knowledge_point` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `qa_record` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `course_id` BIGINT NOT NULL,
  `knowledge_point_id` BIGINT NULL,
  `question` TEXT NOT NULL,
  `answer` TEXT NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_qa_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_qa_course` FOREIGN KEY (`course_id`) REFERENCES `course` (`id`),
  CONSTRAINT `fk_qa_knowledge_point` FOREIGN KEY (`knowledge_point_id`) REFERENCES `knowledge_point` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `wrong_record` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `question_id` BIGINT NULL,
  `course_id` BIGINT NOT NULL,
  `knowledge_point_id` BIGINT NULL,
  `student_answer` TEXT NOT NULL,
  `diagnosis` TEXT NOT NULL,
  `error_type` VARCHAR(128) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_wrong_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_wrong_question` FOREIGN KEY (`question_id`) REFERENCES `question` (`id`),
  CONSTRAINT `fk_wrong_course` FOREIGN KEY (`course_id`) REFERENCES `course` (`id`),
  CONSTRAINT `fk_wrong_knowledge_point` FOREIGN KEY (`knowledge_point_id`) REFERENCES `knowledge_point` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `learning_profile` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `course_id` BIGINT NOT NULL,
  `weak_points_json` JSON NULL,
  `suggestion_json` JSON NULL,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_profile_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_profile_course` FOREIGN KEY (`course_id`) REFERENCES `course` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `teaching_statistics` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `course_id` BIGINT NOT NULL,
  `class_id` VARCHAR(64) NULL,
  `stat_type` VARCHAR(64) NOT NULL,
  `stat_data` JSON NOT NULL,
  `stat_date` DATE NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_teaching_statistics_course` FOREIGN KEY (`course_id`) REFERENCES `course` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
