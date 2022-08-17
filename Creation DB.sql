use ratesrcaping;
CREATE TABLE `comments` (
  `id` int PRIMARY KEY,
  `news_id` int,
  `parent_id` int,
  `username` varchar(255),
  `comment_text` text,
  `date_on` datetime
);

CREATE TABLE `news` (
  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `news_text` text,
  `title` varchar(255),
  `date_on` datetime,
  `author` varchar(255)
);

ALTER TABLE `ratesrcaping`.`news` 
DROP COLUMN `instrument_id`,
CHANGE COLUMN `id` `id` INT NOT NULL AUTO_INCREMENT ;


CREATE TABLE `instrument_news` (
  `id` int PRIMARY KEY,
  `instrument_id` int,
  `news_id` int
);

CREATE TABLE `forum` (
  `id` int PRIMARY KEY,
  `instrument_id` int,
  `parent_id` int,
  `username` varchar(255),
  `post_date` datetime,
  `comment_text` text
);

CREATE TABLE `technical_indicators` (
  `id` int PRIMARY KEY,
  `instrument_id` int,
  `indicator_name` varchar(255),
  `indicator_value` varchar(255),
  `action` varchar(255),
  `date_on` datetime
);

CREATE TABLE `moving_averages` (
  `id` int PRIMARY KEY,
  `instrument_id` int,
  `period` varchar(255),
  `simple_value` float,
  `simple_action` varchar(255),
  `exp_value` float,
  `exp_action` varchar(255),
  `date_on` datetime
);

CREATE TABLE `daily_rates` (
  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY, 
  `instrument_id` int,
  `date_on` datetime,
  `rate` float,
  `open_rate` float,
  `high_rate` float,
  `low_rate` float
);

CREATE TABLE `instruments` (
  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `instrument_name` varchar(255)
);

ALTER TABLE `instrument_news` ADD FOREIGN KEY (`news_id`) REFERENCES `news` (`id`);

ALTER TABLE `forum` ADD FOREIGN KEY (`instrument_id`) REFERENCES `instruments` (`id`);

ALTER TABLE `technical_indicators` ADD FOREIGN KEY (`instrument_id`) REFERENCES `instruments` (`id`);

ALTER TABLE `moving_averages` ADD FOREIGN KEY (`instrument_id`) REFERENCES `instruments` (`id`);

ALTER TABLE `daily_rates` ADD FOREIGN KEY (`instrument_id`) REFERENCES `instruments` (`id`);

ALTER TABLE `instrument_news` ADD FOREIGN KEY (`instrument_id`) REFERENCES `instruments` (`id`);

ALTER TABLE `comments` ADD FOREIGN KEY (`news_id`) REFERENCES `news` (`id`);

ALTER TABLE `comments` ADD FOREIGN KEY (`parent_id`) REFERENCES `comments` (`id`);

ALTER TABLE `forum` ADD FOREIGN KEY (`parent_id`) REFERENCES `forum` (`id`);
