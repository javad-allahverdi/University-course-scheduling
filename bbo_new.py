import yaml
import random
import numpy as np
from copy import deepcopy
from datetime import datetime
from collections import defaultdict

class BBOScheduler:
    """کلاس اصلی برای زمان‌بندی کلاس‌های دانشگاه با استفاده از الگوریتم BBO"""
    
    def __init__(self, config_file):
        """
        مقداردهی اولیه زمان‌بندی
        
        پارامترها:
            config_file (str): مسیر فایل پیکربندی YAML
        """
        # بارگذاری فایل پیکربندی
        with open(config_file, 'r', encoding='utf-8') as file:
            self.config = yaml.safe_load(file)
        
        # تنظیم پارامترهای الگوریتم
        self.setup_algorithm_parameters()
        
        # بارگذاری و آماده‌سازی داده‌ها
        self.load_and_prepare_data()
        
        # دیکشنری برای ردیابی استفاده از مکان‌ها
        self.place_usage = defaultdict(int)
        self.max_place_usage = 5  # حداکثر تعداد کلاس در هر مکان
    
    def setup_algorithm_parameters(self):
        """تنظیم پارامترهای الگوریتم BBO"""
        self.OPTIONS = {
            'popsize': 100,          # تعداد راه‌حل‌ها در جمعیت
            'pmodify': 0.8,          # احتمال تغییر یک راه‌حل
            'pmutate': 0.15,         # افزایش احتمال جهش برای تنوع بیشتر
            'maxgen': 1000,          # افزایش تعداد نسل‌ها برای همگرایی بهتر
            'keep': 5,               # تعداد راه‌حل‌های نخبه
            'lamdalower': 0.0,       # حد پایین نرخ مهاجرت
            'lamdaupper': 1.0,       # حد بالای نرخ مهاجرت
            'dt': 1,                 # گام زمانی
            'I': 1,                  # حداکثر نرخ مهاجرت به جزیره
            'E': 1,                  # حداکثر نرخ مهاجرت از جزیره
            # ضرایب هزینه
            'teacher_conflict_cost': 500,  # افزایش هزینه برای جلوگیری از تداخل
            'place_conflict_cost': 500,    # افزایش هزینه برای جلوگیری از تداخل
            'student_conflict_cost': 50,   # هزینه تداخل دانشجو
            'workload_cost': 50,           # افزایش هزینه برای بارکاری
            'capacity_cost': 30,           # افزایش هزینه برای ظرفیت
            'prereq_cost': 100,            # افزایش هزینه برای پیش‌نیاز
            'coreq_cost': 60,              # هزینه نقض هم‌نیاز
            'maintenance_cost': 100,       # هزینه نقض تعمیرات مکان
            'concurrent_cost': 80,         # هزینه تداخل دروس همزمان
            'teacher_gap_cost': 40,        # هزینه عدم رعایت فاصله زمانی استاد
            'place_usage_cost': 200,       # افزایش هزینه برای توزیع متوازن
            'gender_mismatch_cost': 80,    # هزینه عدم تطابق جنسیت
            'place_overuse_cost': 300      # افزایش هزینه برای استفاده بیش از حد
        }
    
    def load_and_prepare_data(self):
        """بارگذاری و آماده‌سازی داده‌ها از فایل YAML"""
        # بارگذاری داده‌های اصلی
        self.places = {p['code']: p for p in self.config['places']}
        self.teachers = {t['code']: t for t in self.config['teachers']}
        self.courses = {c['code']: c for c in self.config['courses']}
        self.time_slots = {ts['id']: ts for ts in self.config['settings']['time_slots']}
        self.days = self.config['settings']['days_of_week']
        self.constraints = self.config.get('constraints', [])
        
        # آماده‌سازی داده‌ها
        self.prepare_courses_data()
        self.validate_data()
    
    def prepare_courses_data(self):
        """آماده‌سازی داده‌های دروس"""
        self.course_list = [c for c in self.courses.values() if not c.get('fixed', False)]
        
        for course in self.course_list:
            # تنظیم اساتید برای درس
            course['teachers'] = [
                self.teachers[t] for t in course.get('teachers', [])
                if t in self.teachers
            ]
            # تعیین مکان‌های مناسب
            self.set_suitable_places_for_course(course)
        
        # تنظیم پیش‌نیازها و هم‌نیازها
        self.setup_prerequisites()
    
    def set_suitable_places_for_course(self, course):
        """تعیین مکان‌های مناسب برای یک درس"""
        required_type = course.get('required_place_type', 'کلاس تئوری')
        required_place = course.get('required_place', None)
        gender = course.get('gender', 0)
        
        if required_place:
            # اگر مکان خاصی مشخص شده باشد
            course['suitable_places'] = [
                p for p in self.places.values()
                if p['code'] in required_place.split(',')
            ]
        else:
            course['suitable_places'] = [
                p for p in self.places.values()
                if p['type'] == required_type and
                (gender == 0 or p['gender'] == 0 or p['gender'] == gender) and
                p['available']
            ]
    
    def setup_prerequisites(self):
        """تنظیم ساختار پیش‌نیازها و هم‌نیازها"""
        self.prerequisites = {c['code']: c.get('prerequisites', []) for c in self.course_list}
        self.corequisites = {c['code']: c.get('corequisites', []) for c in self.course_list}
    
    def validate_data(self):
        """اعتبارسنجی داده‌های ورودی"""
        limited_places_courses = []
        for course in self.course_list:
            if not course['suitable_places']:
                print(f"⚠️ هشدار: برای درس '{course['name']}' هیچ مکان مناسبی یافت نشد!")
                limited_places_courses.append((course['name'], 0))
            else:
                num_places = len(course['suitable_places'])
                print(f"درس '{course['name']}': مکان‌های مناسب = {[p['code'] for p in course['suitable_places']]}")
                if num_places <= 2:
                    limited_places_courses.append((course['name'], num_places))
            if not course.get('teachers', []):
                print(f"⚠️ هشدار: برای درس '{course['name']}' هیچ استاد مناسبی یافت نشد!")
        
        if limited_places_courses:
            print("\n⚠️ دروس با مکان‌های محدود:")
            for course_name, num_places in limited_places_courses:
                print(f"- {course_name}: {num_places} مکان مناسب")
    
    def initialize_population(self):
        """ایجاد جمعیت اولیه از زمان‌بندی‌های تصادفی"""
        population = []
        
        for _ in range(self.OPTIONS['popsize']):
            schedule = {'courses': [], 'cost': float('inf')}
            self.place_usage.clear()  # ریست کردن آمار استفاده از مکان‌ها
            
            # ابتدا دروس با مکان‌های خاص (مثلاً سالن شطرنج) را تخصیص می‌دهیم
            for course in sorted(self.course_list, key=lambda c: len(c['suitable_places'])):
                teacher = self.select_random_teacher_for_course(course)
                place = self.select_balanced_place_for_course(course, schedule)
                if not teacher or not place:
                    continue
                
                slot_id = random.choice(list(self.time_slots.keys()))
                day = random.randint(1, len(self.days))
                
                schedule['courses'].append({
                    'course_code': course['code'],
                    'teacher_code': teacher['code'],
                    'place_code': place['code'],
                    'slot_id': slot_id,
                    'day': day
                })
                self.place_usage[place['code']] += 1
            
            schedule = self.fix_schedule_conflicts(schedule)
            population.append(schedule)
        
        return population
    
    def select_random_teacher_for_course(self, course):
        """انتخاب تصادفی استاد برای یک درس"""
        suitable_teachers = course['teachers']
        return random.choice(suitable_teachers) if suitable_teachers else None
    
    def select_balanced_place_for_course(self, course, schedule):
        """انتخاب مکان با اولویت مکان‌های کمتر استفاده‌شده"""
        suitable_places = course['suitable_places']
        if not suitable_places:
            return None
        
        # محاسبه وزن برای هر مکان بر اساس تعداد استفاده
        weights = []
        max_usage = max(self.place_usage.values()) if self.place_usage else 0
        for place in suitable_places:
            usage_count = self.place_usage[place['code']]
            # اگر مکان بیش از حد مجاز استفاده شده، وزن صفر می‌دهیم
            if usage_count >= self.max_place_usage:
                weight = 0.0
            else:
                # وزن معکوس با جریمه بسیار قوی
                weight = 1.0 / (1.0 + usage_count * 10.0) if max_usage < 10 else 1.0 / (1.0 + usage_count * 20.0)
            weights.append(weight)
        
        # اگر همه وزن‌ها صفر بودند، مکان تصادفی انتخاب می‌کنیم
        if sum(weights) == 0:
            available_places = [p for p in suitable_places if self.place_usage[p['code']] < self.max_place_usage]
            return random.choice(available_places) if available_places else random.choice(suitable_places)
        
        # نرمال‌سازی وزن‌ها
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]
        
        # انتخاب مکان با احتمال وزن‌دهی‌شده
        return random.choices(suitable_places, weights=weights, k=1)[0]
    
    def cost_function(self, population):
        """محاسبه هزینه هر زمان‌بندی در جمعیت"""
        for schedule in population:
            cost = 0
            cost += self.calculate_teacher_conflicts(schedule)
            cost += self.calculate_place_conflicts(schedule)
            cost += self.calculate_workload_issues(schedule)
            cost += self.calculate_capacity_issues(schedule)
            cost += self.calculate_prerequisite_violations(schedule)
            cost += self.calculate_corequisite_violations(schedule)
            cost += self.calculate_maintenance_violations(schedule)
            cost += self.calculate_concurrent_course_violations(schedule)
            cost += self.calculate_teacher_gap_violations(schedule)
            cost += self.calculate_place_usage_imbalance(schedule)
            cost += self.calculate_gender_mismatch(schedule)
            cost += self.calculate_place_overuse(schedule)
            schedule['cost'] = cost
        
        return population
    
    def calculate_teacher_conflicts(self, schedule):
        """محاسبه هزینه تداخل استادان"""
        teacher_slots = defaultdict(list)
        conflict_cost = 0
        
        for course in schedule['courses']:
            teacher = course['teacher_code']
            slot = course['slot_id']
            day = course['day']
            slot_key = (day, slot)
            
            if slot_key in teacher_slots[teacher]:
                conflict_cost += self.OPTIONS['teacher_conflict_cost']
            teacher_slots[teacher].append(slot_key)
        
        return conflict_cost
    
    def calculate_place_conflicts(self, schedule):
        """محاسبه هزینه تداخل مکان‌ها"""
        place_slots = defaultdict(list)
        conflict_cost = 0
        
        for course in schedule['courses']:
            place = course['place_code']
            slot = course['slot_id']
            day = course['day']
            slot_key = (day, slot)
            
            if slot_key in place_slots[place]:
                conflict_cost += self.OPTIONS['place_conflict_cost']
            place_slots[place].append(slot_key)
        
        return conflict_cost
    
    def calculate_workload_issues(self, schedule):
        """محاسبه هزینه بارکاری نامناسب استادان"""
        teacher_units = defaultdict(int)
        workload_cost = 0
        
        for course in schedule['courses']:
            teacher = course['teacher_code']
            units = self.courses[course['course_code']]['units']
            teacher_units[teacher] += units
        
        for teacher, units in teacher_units.items():
            min_units = self.teachers[teacher]['min_units']
            max_units = self.teachers[teacher]['max_units']
            
            if units < min_units or units > max_units:
                workload_cost += self.OPTIONS['workload_cost']
        
        return workload_cost
    
    def calculate_capacity_issues(self, schedule):
        """محاسبه هزینه عدم تناسب ظرفیت کلاس‌ها"""
        capacity_cost = 0
        
        for course in schedule['courses']:
            place_capacity = self.places[course['place_code']]['capacity']
            expected_students = self.courses[course['course_code']].get('expected_students', 30)
            
            if place_capacity < expected_students:
                capacity_cost += self.OPTIONS['capacity_cost']
        
        return capacity_cost
    
    def calculate_prerequisite_violations(self, schedule):
        """محاسبه هزینه نقض پیش‌نیازها"""
        violation_cost = 0
        
        for course in schedule['courses']:
            course_code = course['course_code']
            course_slot = course['slot_id']
            course_day = course['day']
            
            for prereq in self.prerequisites.get(course_code, []):
                if not self.is_prerequisite_satisfied(prereq, course_day, course_slot, schedule):
                    violation_cost += self.OPTIONS['prereq_cost']
        
        return violation_cost
    
    def calculate_corequisite_violations(self, schedule):
        """محاسبه هزینه نقض هم‌نیازها"""
        violation_cost = 0
        
        for course in schedule['courses']:
            course_code = course['course_code']
            course_slot = course['slot_id']
            course_day = course['day']
            
            for coreq in self.corequisites.get(course_code, []):
                if not self.is_corequisite_satisfied(coreq, course_day, course_slot, schedule):
                    violation_cost += self.OPTIONS['coreq_cost']
        
        return violation_cost
    
    def calculate_maintenance_violations(self, schedule):
        """محاسبه هزینه نقض محدودیت تعمیرات مکان"""
        violation_cost = 0
        
        for constraint in self.constraints:
            if constraint['type'] != 'place_maintenance':
                continue
                
            place_code = constraint['place_code']
            start_date = datetime.strptime(constraint['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(constraint['end_date'], '%Y-%m-%d')
            
            for course in schedule['courses']:
                if course['place_code'] != place_code:
                    continue
                    
                # فرض می‌کنیم زمان‌بندی در بازه ترم بهار 1403 است
                course_date = datetime(2024, 4, 1 + (course['day'] - 1))  # تقریبی
                if start_date <= course_date <= end_date:
                    violation_cost += self.OPTIONS['maintenance_cost']
        
        return violation_cost
    
    def calculate_concurrent_course_violations(self, schedule):
        """محاسبه هزینه تداخل دروس همزمان"""
        violation_cost = 0
        
        for constraint in self.constraints:
            if constraint['type'] != 'concurrent_courses':
                continue
                
            course_codes = constraint['course_codes']
            max_concurrent = constraint['max_concurrent']
            
            slot_courses = defaultdict(list)
            for course in schedule['courses']:
                if course['course_code'] in course_codes:
                    slot_key = (course['day'], course['slot_id'])
                    slot_courses[slot_key].append(course['course_code'])
            
            for slot, courses in slot_courses.items():
                if len(courses) > max_concurrent:
                    violation_cost += self.OPTIONS['concurrent_cost'] * (len(courses) - max_concurrent)
        
        return violation_cost
    
    def calculate_teacher_gap_violations(self, schedule):
        """محاسبه هزینه عدم رعایت فاصله زمانی بین کلاس‌های استاد"""
        violation_cost = 0
        
        for constraint in self.constraints:
            if constraint['type'] != 'same_teacher_courses':
                continue
                
            teacher_code = constraint['teacher_code']
            min_hours = constraint['min_hours_between']
            
            teacher_courses = [
                c for c in schedule['courses'] if c['teacher_code'] == teacher_code
            ]
            
            for i, course1 in enumerate(teacher_courses):
                for course2 in teacher_courses[i+1:]:
                    if course1['day'] != course2['day']:
                        continue
                        
                    slot1 = self.time_slots[course1['slot_id']]['start']
                    slot2 = self.time_slots[course2['slot_id']]['start']
                    
                    time1 = datetime.strptime(slot1, '%H:%M')
                    time2 = datetime.strptime(slot2, '%H:%M')
                    hours_diff = abs((time2 - time1).total_seconds()) / 3600
                    
                    if hours_diff < min_hours:
                        violation_cost += self.OPTIONS['teacher_gap_cost']
        
        return violation_cost
    
    def calculate_place_usage_imbalance(self, schedule):
        """محاسبه هزینه عدم توزیع متوازن استفاده از مکان‌ها"""
        usage_counts = defaultdict(int)
        for course in schedule['courses']:
            usage_counts[course['place_code']] += 1
        
        if not usage_counts:
            return 0
        
        max_usage = max(usage_counts.values())
        min_usage = min(usage_counts.values())
        imbalance = max_usage - min_usage
        
        return imbalance * self.OPTIONS['place_usage_cost']
    
    def calculate_place_overuse(self, schedule):
        """محاسبه هزینه استفاده بیش از حد از یک مکان"""
        usage_counts = defaultdict(int)
        for course in schedule['courses']:
            usage_counts[course['place_code']] += 1
        
        overuse_cost = 0
        avg_usage = sum(usage_counts.values()) / len(usage_counts) if usage_counts else 0
        for count in usage_counts.values():
            if count > avg_usage * 1.5 or count > self.max_place_usage:
                overuse_cost += (count - avg_usage) * self.OPTIONS['place_overuse_cost']
        
        return overuse_cost
    
    def calculate_gender_mismatch(self, schedule):
        """محاسبه هزینه عدم تطابق جنسیت و تداخل زمانی کلاس‌های خانم‌ها و آقایان"""
        mismatch_cost = 0
        slot_gender = defaultdict(list)
        
        for course in schedule['courses']:
            course_gender = self.courses[course['course_code']].get('gender', 0)
            place_gender = self.places[course['place_code']].get('gender', 0)
            teacher_gender = self.teachers[course['teacher_code']].get('gender', 0)
            slot_key = (course['day'], course['slot_id'], course['place_code'])
            
            # بررسی تطابق جنسیت درس، استاد، و مکان
            if course_gender != 0:
                if place_gender != 0 and place_gender != course_gender:
                    mismatch_cost += self.OPTIONS['gender_mismatch_cost']
                if teacher_gender != course_gender:
                    mismatch_cost += self.OPTIONS['gender_mismatch_cost']
            
            # بررسی تداخل زمانی کلاس‌های خانم‌ها و آقایان
            if course_gender != 0:
                slot_gender[slot_key].append(course_gender)
        
        # جریمه برای تداخل جنسیتی در یک اسلات و مکان
        for slot_key, genders in slot_gender.items():
            if len(set(genders)) > 1:
                mismatch_cost += self.OPTIONS['gender_mismatch_cost']
        
        return mismatch_cost
    
    def is_prerequisite_satisfied(self, prereq_code, current_day, current_slot, schedule):
        """بررسی آیا پیش‌نیاز برقرار است"""
        for c in schedule['courses']:
            if c['course_code'] == prereq_code:
                return c['day'] < current_day or (c['day'] == current_day and c['slot_id'] < current_slot)
        return False
    
    def is_corequisite_satisfied(self, coreq_code, current_day, current_slot, schedule):
        """بررسی آیا هم‌نیاز برقرار است"""
        for c in schedule['courses']:
            if c['course_code'] == coreq_code:
                return c['day'] == current_day and abs(c['slot_id'] - current_slot) <= 1
        return False
    
    def fix_schedule_conflicts(self, schedule):
        """رفع تداخل‌های زمانی در زمان‌بندی"""
        teacher_slots = defaultdict(list)
        place_slots = defaultdict(list)
        
        # جمع‌آوری تمام تخصیص‌های زمانی
        for course in schedule['courses']:
            slot_key = (course['day'], course['slot_id'])
            teacher_slots[course['teacher_code']].append((slot_key, course))
            place_slots[course['place_code']].append((slot_key, course))
        
        # رفع تداخل‌های استاد
        for teacher, slots in teacher_slots.items():
            slot_counts = defaultdict(list)
            for slot_key, course in slots:
                slot_counts[slot_key].append(course)
            
            for slot_key, courses in slot_counts.items():
                if len(courses) > 1:
                    for course in courses[1:]:
                        self.reassign_course_slot(course, schedule)
        
        # رفع تداخل‌های مکان
        for place, slots in place_slots.items():
            slot_counts = defaultdict(list)
            for slot_key, course in slots:
                slot_counts[slot_key].append(course)
            
            for slot_key, courses in slot_counts.items():
                if len(courses) > 1:
                    for course in courses[1:]:
                        self.reassign_course_slot(course, schedule)
        
        return schedule
    
    def reassign_course_slot(self, course, schedule):
        """تخصیص مجدد اسلات زمانی برای رفع تداخل"""
        available_slots = list(self.time_slots.keys())
        available_days = list(range(1, len(self.days) + 1))
        
        random.shuffle(available_slots)
        random.shuffle(available_days)
        
        max_attempts = 50  # افزایش تعداد تلاش‌ها
        for _ in range(max_attempts):
            for new_slot in available_slots:
                for new_day in available_days:
                    new_slot_key = (new_day, new_slot)
                    
                    # بررسی عدم تداخل با استاد
                    teacher_conflict = False
                    for other_course in schedule['courses']:
                        if other_course is course:
                            continue
                        if other_course['teacher_code'] == course['teacher_code']:
                            if (other_course['day'], other_course['slot_id']) == new_slot_key:
                                teacher_conflict = True
                                break
                    
                    # بررسی عدم تداخل با مکان
                    place_conflict = False
                    for other_course in schedule['courses']:
                        if other_course is course:
                            continue
                        if other_course['place_code'] == course['place_code']:
                            if (other_course['day'], other_course['slot_id']) == new_slot_key:
                                place_conflict = True
                                break
                    
                    if not teacher_conflict and not place_conflict:
                        course['slot_id'] = new_slot
                        course['day'] = new_day
                        return
        
        # اگر اسلات بدون تداخل یافت نشد، مکان را تغییر دهید
        new_place = self.select_balanced_place_for_course(self.courses[course['course_code']], schedule)
        if new_place:
            self.place_usage[course['place_code']] -= 1
            course['place_code'] = new_place['code']
            self.place_usage[course['place_code']] += 1
            self.reassign_course_slot(course, schedule)
    
    def feasible_function(self, population):
        """بررسی و اصلاح راه‌حل‌های غیرممکن"""
        for schedule in population:
            for course in schedule['courses']:
                self.fix_course_issues(course)
            schedule = self.fix_schedule_conflicts(schedule)
        
        return population
    
    def fix_course_issues(self, course):
        """اصلاح مشکلات یک کلاس"""
        self.fix_teacher_gender_issue(course)
        self.fix_place_gender_issue(course)
    
    def fix_teacher_gender_issue(self, course):
        """اصلاح مشکل تطابق جنسیت استاد و درس"""
        course_gender = self.courses[course['course_code']].get('gender', 0)
        teacher_gender = self.teachers[course['teacher_code']].get('gender', 0)
        
        if course_gender != 0 and teacher_gender != course_gender:
            suitable_teachers = [
                t for t in self.teachers.values()
                if course['course_code'] in t.get('courses', []) and
                t.get('gender', 0) == course_gender
            ]
            if suitable_teachers:
                course['teacher_code'] = random.choice(suitable_teachers)['code']
    
    def fix_place_gender_issue(self, course):
        """اصلاح مشکل تطابق جنسیت دانشجویان و مکان"""
        course_gender = self.courses[course['course_code']].get('gender', 0)
        place_gender = self.places[course['place_code']].get('gender', 0)
        
        if course_gender != 0 and place_gender != 0 and place_gender != course_gender:
            suitable_places = self.courses[course['course_code']]['suitable_places']
            if suitable_places:
                course['place_code'] = self.select_balanced_place_for_course(
                    self.courses[course['course_code']], {}
                )['code']
    
    def migration(self, population, lambda_rates, mu_rates):
        """عملگر مهاجرت در الگوریتم BBO"""
        for i, schedule in enumerate(population):
            if random.random() > self.OPTIONS['pmodify']:
                continue
            
            lambda_scale = self.calculate_normalized_migration_rate(lambda_rates, i)
            
            for j in range(len(schedule['courses'])):
                if random.random() < lambda_scale:
                    self.apply_migration(schedule, j, population, mu_rates)
        
        return population
    
    def calculate_normalized_migration_rate(self, lambda_rates, index):
        """محاسبه نرخ مهاجرت نرمال‌شده"""
        lambda_min = min(lambda_rates)
        lambda_max = max(lambda_rates)
        if lambda_max == lambda_min:
            return self.OPTIONS['lamdaupper']
        return self.OPTIONS['lamdalower'] + (
            self.OPTIONS['lamdaupper'] - self.OPTIONS['lamdalower']
        ) * (lambda_rates[index] - lambda_min) / (lambda_max - lambda_min)
    
    def apply_migration(self, schedule, feature_index, population, mu_rates):
        """اعمال مهاجرت روی یک ویژگی خاص"""
        source_index = self.select_migration_source(population, mu_rates)
        schedule['courses'][feature_index] = deepcopy(population[source_index]['courses'][feature_index])
    
    def select_migration_source(self, population, mu_rates):
        """انتخاب منبع مهاجرت با روش چرخ رولت"""
        total_mu = sum(mu_rates)
        if total_mu == 0:
            return random.randint(0, len(population) - 1)
        
        rand_num = random.random() * total_mu
        select_sum = 0
        
        for i, mu in enumerate(mu_rates):
            select_sum += mu
            if rand_num <= select_sum:
                return i
        return len(population) - 1

    def mutation(self, population):
        """عملگر جهش در الگوریتم BBO"""
        population = sorted(population, key=lambda x: x['cost'])
        half = len(population) // 2
        
        for i in range(half, len(population)):
            self.place_usage.clear()
            for course in population[i]['courses']:
                self.place_usage[course['place_code']] += 1
            for j in range(len(population[i]['courses'])):
                if random.random() < self.OPTIONS['pmutate']:
                    self.mutate_course(population[i]['courses'][j])
        
        return population
    
    def mutate_course(self, course):
        """اعمال جهش روی یک کلاس"""
        course_info = self.courses[course['course_code']]
        
        # جهش استاد
        teacher = self.select_random_teacher_for_course(course_info)
        if teacher:
            course['teacher_code'] = teacher['code']
        
        # جهش مکان
        place = self.select_balanced_place_for_course(course_info, {})
        if place:
            self.place_usage[course['place_code']] -= 1
            course['place_code'] = place['code']
            self.place_usage[course['place_code']] += 1
        
        # جهش زمان
        course['slot_id'] = random.choice(list(self.time_slots.keys()))
        course['day'] = random.randint(1, len(self.days))
    
    def get_species_counts(self, population):
        """محاسبه تعداد گونه‌ها برای هر راه‌حل"""
        population = sorted(population, key=lambda x: x['cost'])
        p = len(population)
        for i, h in enumerate(population):
            h['SpeciesCount'] = p - i
        return population
    
    def get_lambda_mu(self, population):
        """محاسبه نرخ‌های مهاجرت و مهاجرت"""
        P = len(population)
        lambda_rates = [self.OPTIONS['I'] * (1 - (h['SpeciesCount'] / P)) for h in population]
        mu_rates = [self.OPTIONS['E'] * (h['SpeciesCount'] / P) for h in population]
        return lambda_rates, mu_rates

    def run_algorithm(self):
        """اجرای اصلی الگوریتم BBO"""
        population = self.initialize_population()
        population = self.cost_function(population)
        population = sorted(population, key=lambda x: x['cost'])
        
        best_schedule = deepcopy(population[0])
        best_cost = best_schedule['cost']
        
        for gen in range(self.OPTIONS['maxgen']):
            elites = deepcopy(population[:self.OPTIONS['keep']])
            population = self.get_species_counts(population)
            lambda_rates, mu_rates = self.get_lambda_mu(population)
            
            population = self.migration(population, lambda_rates, mu_rates)
            population = self.mutation(population)
            population = self.feasible_function(population)
            population = self.cost_function(population)
            population = sorted(population, key=lambda x: x['cost'])
            
            for i in range(self.OPTIONS['keep']):
                population[-(i+1)] = deepcopy(elites[i])
            
            if population[0]['cost'] < best_cost:
                best_schedule = deepcopy(population[0])
                best_cost = best_schedule['cost']
            
            print(f"نسل {gen+1}: بهترین هزینه = {best_cost}")
        
        return best_schedule

    def save_schedule_to_file(self, schedule, filename="schedule_output.txt"):
        """ذخیره زمان‌بندی نهایی در فایل متنی"""
        with open(filename, 'w', encoding='utf-8') as file:
            file.write("زمان‌بندی بهینه کلاس‌های دانشگاه تربیت بدنی - بهار 1403\n")
            file.write("=" * 100 + "\n")
            file.write(f"{'روز':<10}{'زمان':<15}{'درس':<35}{'استاد':<30}{'مکان':<20}{'ظرفیت':<10}{'جنسیت':<10}\n")
            file.write("-" * 100 + "\n")
            
            sorted_courses = sorted(
                schedule['courses'],
                key=lambda x: (x['day'], self.time_slots[x['slot_id']]['start'])
            )
            
            for course in sorted_courses:
                day = self.days[course['day']-1]
                time = f"{self.time_slots[course['slot_id']]['start']}-{self.time_slots[course['slot_id']]['end']}"
                course_name = self.courses[course['course_code']]['name'][:34]
                teacher_name = self.teachers[course['teacher_code']]['full_name'][:29]
                place_name = self.places[course['place_code']]['name'][:19]
                place_capacity = self.places[course['place_code']]['capacity']
                course_gender = self.courses[course['course_code']].get('gender', 0)
                gender_str = 'خانم' if course_gender == 2 else 'آقا' if course_gender == 1 else 'مشترک'
                
                file.write(f"{day:<10}{time:<15}{course_name:<35}{teacher_name:<30}{place_name:<20}{place_capacity:<10}{gender_str:<10}\n")
            
            file.write("\n" + "=" * 100 + "\n")
            file.write(f"هزینه نهایی زمان‌بندی: {schedule['cost']}\n")
            file.write(f"تعداد کلاس‌ها: {len(schedule['courses'])}\n")
            
            teacher_stats = self.calculate_teacher_statistics(schedule)
            file.write("\nآمار تدریس اساتید:\n")
            file.write("-" * 50 + "\n")
            for teacher_code, count in sorted(teacher_stats.items(), key=lambda x: -x[1]):
                teacher_name = self.teachers[teacher_code]['full_name']
                file.write(f"{teacher_name:<30}: {count} کلاس\n")
            
            place_stats = self.calculate_place_statistics(schedule)
            file.write("\nآمار استفاده از مکان‌ها:\n")
            file.write("-" * 50 + "\n")
            for place_code, count in sorted(place_stats.items(), key=lambda x: -x[1]):
                place_name = self.places[place_code]['name']
                file.write(f"{place_name:<30}: {count} کلاس\n")
            
            file.write("\nمحدودیت‌های نقض‌شده:\n")
            file.write("-" * 50 + "\n")
            violations = [
                (self.calculate_teacher_conflicts(schedule) // self.OPTIONS['teacher_conflict_cost'], "تداخل زمان استادان"),
                (self.calculate_place_conflicts(schedule) // self.OPTIONS['place_conflict_cost'], "تداخل زمان مکان‌ها"),
                (self.calculate_workload_issues(schedule) // self.OPTIONS['workload_cost'], "مشکل در بار کاری استادان"),
                (self.calculate_capacity_issues(schedule) // self.OPTIONS['capacity_cost'], "عدم تناسب ظرفیت کلاس‌ها"),
                (self.calculate_prerequisite_violations(schedule) // self.OPTIONS['prereq_cost'], "نقض پیش‌نیازها"),
                (self.calculate_corequisite_violations(schedule) // self.OPTIONS['coreq_cost'], "نقض هم‌نیازها"),
                (self.calculate_maintenance_violations(schedule) // self.OPTIONS['maintenance_cost'], "نقض تعمیرات مکان"),
                (self.calculate_concurrent_course_violations(schedule) // self.OPTIONS['concurrent_cost'], "تداخل دروس همزمان"),
                (self.calculate_teacher_gap_violations(schedule) // self.OPTIONS['teacher_gap_cost'], "عدم رعایت فاصله زمانی استاد"),
                (self.calculate_place_usage_imbalance(schedule) // self.OPTIONS['place_usage_cost'], "عدم توزیع متوازن مکان‌ها"),
                (self.calculate_place_overuse(schedule) // self.OPTIONS['place_overuse_cost'], "استفاده بیش از حد از یک مکان"),
                (self.calculate_gender_mismatch(schedule) // self.OPTIONS['gender_mismatch_cost'], "عدم تطابق جنسیت یا تداخل زمانی")
            ]
            
            for count, desc in violations:
                if count > 0:
                    file.write(f"- {desc}: {count} مورد\n")
            if not any(count > 0 for count, _ in violations):
                file.write("هیچ محدودیتی نقض نشده است.\n")
            
            # گزارش تداخل‌های خاص
            file.write("\nگزارش تداخل‌های خاص:\n")
            file.write("-" * 50 + "\n")
            teacher_conflicts = self.get_teacher_conflicts(schedule)
            place_conflicts = self.get_place_conflicts(schedule)
            
            if teacher_conflicts:
                file.write("تداخل‌های استادان:\n")
                for teacher, slots in teacher_conflicts.items():
                    file.write(f"استاد {self.teachers[teacher]['full_name']}:\n")
                    for slot, courses in slots.items():
                        file.write(f"  اسلات {slot}: {[self.courses[c['course_code']]['name'] for c in courses]}\n")
            else:
                file.write("هیچ تداخل استادی یافت نشد.\n")
            
            if place_conflicts:
                file.write("تداخل‌های مکان‌ها:\n")
                for place, slots in place_conflicts.items():
                    file.write(f"مکان {self.places[place]['name']}:\n")
                    for slot, courses in slots.items():
                        file.write(f"  اسلات {slot}: {[self.courses[c['course_code']]['name'] for c in courses]}\n")
            else:
                file.write("هیچ تداخل مکانی یافت نشد.\n")
            
            file.write("\nپایان فایل زمان‌بندی\n")
    
    def get_teacher_conflicts(self, schedule):
        """یافتن تداخل‌های خاص استادان"""
        teacher_slots = defaultdict(list)
        conflicts = defaultdict(lambda: defaultdict(list))
        
        for course in schedule['courses']:
            teacher = course['teacher_code']
            slot = (course['day'], course['slot_id'])
            teacher_slots[(teacher, slot)].append(course)
        
        for (teacher, slot), courses in teacher_slots.items():
            if len(courses) > 1:
                conflicts[teacher][slot] = courses
        
        return conflicts
    
    def get_place_conflicts(self, schedule):
        """یافتن تداخل‌های خاص مکان‌ها"""
        place_slots = defaultdict(list)
        conflicts = defaultdict(lambda: defaultdict(list))
        
        for course in schedule['courses']:
            place = course['place_code']
            slot = (course['day'], course['slot_id'])
            place_slots[(place, slot)].append(course)
        
        for (place, slot), courses in place_slots.items():
            if len(courses) > 1:
                conflicts[place][slot] = courses
        
        return conflicts
    
    def calculate_teacher_statistics(self, schedule):
        """محاسبه آمار تدریس اساتید"""
        teacher_stats = defaultdict(int)
        for course in schedule['courses']:
            teacher_stats[course['teacher_code']] += 1
        return teacher_stats
    
    def calculate_place_statistics(self, schedule):
        """محاسبه آمار استفاده از مکان‌ها"""
        place_stats = defaultdict(int)
        for course in schedule['courses']:
            place_stats[course['place_code']] += 1
        return place_stats
    
    def print_schedule(self, schedule):
        """چاپ زمان‌بندی نهایی در کنسول"""
        print("\nزمان‌بندی بهینه کلاس‌ها:")
        print("=" * 100)
        print(f"{'روز':<10}{'زمان':<15}{'درس':<35}{'استاد':<30}{'مکان':<20}{'ظرفیت':<10}{'جنسیت':<10}")
        print("-" * 100)
        
        sorted_courses = sorted(
            schedule['courses'],
            key=lambda x: (x['day'], self.time_slots[x['slot_id']]['start'])
        )
        
        for course in sorted_courses:
            day = self.days[course['day']-1]
            time = f"{self.time_slots[course['slot_id']]['start']}-{self.time_slots[course['slot_id']]['end']}"
            course_name = self.courses[course['course_code']]['name'][:34]
            teacher_name = self.teachers[course['teacher_code']]['full_name'][:29]
            place_name = self.places[course['place_code']]['name'][:19]
            place_capacity = self.places[course['place_code']]['capacity']
            course_gender = self.courses[course['course_code']].get('gender', 0)
            gender_str = 'خانم' if course_gender == 2 else 'آقا' if course_gender == 1 else 'مشترک'
            
            print(f"{day:<10}{time:<15}{course_name:<35}{teacher_name:<30}{place_name:<20}{place_capacity:<10}{gender_str:<10}")
        
        print("\nهزینه نهایی:", schedule['cost'])
        
        # چاپ آمار مکان‌ها در کنسول
        place_stats = self.calculate_place_statistics(schedule)
        print("\nآمار استفاده از مکان‌ها:")
        print("-" * 50)
        for place_code, count in sorted(place_stats.items(), key=lambda x: -x[1]):
            place_name = self.places[place_code]['name']
            print(f"{place_name:<30}: {count} کلاس")

if __name__ == "__main__":
    scheduler = BBOScheduler("config.yaml")
    print("شروع اجرای الگوریتم BBO برای زمان‌بندی کلاس‌ها...")
    best_schedule = scheduler.run_algorithm()
    output_file = "final_schedule.txt"
    scheduler.save_schedule_to_file(best_schedule, output_file)
    print(f"\nنتایج زمان‌بندی در فایل '{output_file}' ذخیره شد.")
    scheduler.print_schedule(best_schedule)