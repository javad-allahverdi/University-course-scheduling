CREATE TABLE places (
    place_code VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255),
    capacity INTEGER,
    sex SMALLINT, -- 1: male, 2: female, 0: both
    available INTEGER
);

CREATE TABLE teachers (
    teacher_code VARCHAR(255) PRIMARY KEY,
    full_name VARCHAR(255),
    position SMALLINT,
    employment_type SMALLINT,
    max_duty SMALLINT,
    min_duty SMALLINT,
    degree SMALLINT,
    sex SMALLINT,
    courses INTEGER -- تعداد درس‌هایی که می‌تواند تدریس کند
);

CREATE TABLE courses (
    course_code VARCHAR(255) PRIMARY KEY,
    course_name VARCHAR(255),
    credit SMALLINT,
    maghtah SMALLINT, -- مقطع تحصیلی
    course_type SMALLINT, -- نوع درس
    prerequisites INTEGER[], -- پیش‌نیازها
    corequisites INTEGER[], -- هم‌نیازها
    required_place_type VARCHAR(255),
    sex SMALLINT -- جنسیت دانشجویان
);

CREATE TABLE course_schedule (
    schedule_id SERIAL PRIMARY KEY,
    course_code VARCHAR(255) NOT NULL REFERENCES courses(course_code),
    group_num SMALLINT NOT NULL,
    teacher_code VARCHAR(255) NOT NULL REFERENCES teachers(teacher_code),
    place_code VARCHAR(255) NOT NULL REFERENCES places(place_code),
    slot_id INTEGER NOT NULL REFERENCES time_slots(slot_id),
    teacher_sex SMALLINT,
    students_sex SMALLINT,
    capacity INTEGER,
    -- اضافه کردن محدودیت کلید اصلی ترکیبی جدید
    UNIQUE (course_code, group_num),
    -- اضافه کردن محدودیت‌های دیگر
    UNIQUE (teacher_code, slot_id),  -- یک استاد نمی‌تواند در یک زمان در دو کلاس باشد
    UNIQUE (place_code, slot_id)     -- یک مکان نمی‌تواند در یک زمان برای دو کلاس باشد
);

CREATE TABLE time_slots (
    slot_id SERIAL PRIMARY KEY,
    day SMALLINT, -- 1-7 برای روزهای هفته
    start_time TIME,
    end_time TIME
);

