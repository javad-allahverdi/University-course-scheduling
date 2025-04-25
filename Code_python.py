import yaml
import random
import numpy as np
from datetime import datetime
import psycopg2

class CourseSchedulingProblem:
    def __init__(self, config_file):
        with open(config_file, 'r') as file:
            self.config = yaml.safe_load(file)
        
        # Connect to PostgreSQL
        self.conn = psycopg2.connect(
            dbname="university",
            user="postgres",
            password="postgres",
            host="localhost"
        )
        
        # Load data from database
        self.load_data()
        
        # BBO options
        self.OPTIONS = {
            'popsize': 50,
            'pmodify': 0.7,
            'pmutate': 0.01,
            'maxgen': 100,
            'keep': 2,
            'lamdalower': 0.0,
            'lamdaupper': 1,
            'dt': 1,
            'I': 1,
            'E': 1
        }
    
    def load_data(self):
        """Load data from PostgreSQL database"""
        cur = self.conn.cursor()
        
        # Load courses
        cur.execute("SELECT * FROM courses")
        self.courses = {row[0]: row for row in cur.fetchall()}
        
        # Load teachers
        cur.execute("SELECT * FROM teachers")
        self.teachers = {row[0]: row for row in cur.fetchall()}
        
        # Load places
        cur.execute("SELECT * FROM places")
        self.places = {row[0]: row for row in cur.fetchall()}
        
        # Load time slots
        cur.execute("SELECT * FROM time_slots")
        self.time_slots = {row[0]: row for row in cur.fetchall()}
        
        cur.close()
    
    def cost_function(self, population):
        """Calculate cost for each schedule in population"""
        for schedule in population:
            cost = 0
            
            # Check teacher availability
            teacher_conflicts = self.check_teacher_conflicts(schedule)
            cost += teacher_conflicts * 100
            
            # Check place availability
            place_conflicts = self.check_place_conflicts(schedule)
            cost += place_conflicts * 50
            
            # Check student conflicts
            student_conflicts = self.check_student_conflicts(schedule)
            cost += student_conflicts * 30
            
            # Check teacher workload
            workload_issues = self.check_teacher_workload(schedule)
            cost += workload_issues * 20
            
            # Check room capacity
            capacity_issues = self.check_room_capacity(schedule)
            cost += capacity_issues * 10
            
            schedule['cost'] = cost
        
        return population
    
    def check_teacher_conflicts(self, schedule):
        """Check if a teacher is scheduled for multiple classes at the same time"""
        conflicts = 0
        teacher_slots = {}
        
        for course in schedule['courses']:
            teacher = course['teacher_code']
            slot = course['slot_id']
            
            if teacher in teacher_slots:
                if slot in teacher_slots[teacher]:
                    conflicts += 1
                else:
                    teacher_slots[teacher].append(slot)
            else:
                teacher_slots[teacher] = [slot]
        
        return conflicts
    
    def check_place_conflicts(self, schedule):
        """Check if a place is used for multiple classes at the same time"""
        conflicts = 0
        place_slots = {}
        
        for course in schedule['courses']:
            place = course['place_code']
            slot = course['slot_id']
            
            if place in place_slots:
                if slot in place_slots[place]:
                    conflicts += 1
                else:
                    place_slots[place].append(slot)
            else:
                place_slots[place] = [slot]
        
        return conflicts
    
    def check_student_conflicts(self, schedule):
        """Check if students have conflicting classes"""
        # This is a simplified version - in reality would need student enrollment data
        conflicts = 0
        return conflicts
    
    def check_teacher_workload(self, schedule):
        """Check if teachers are within their min/max duty limits"""
        issues = 0
        teacher_load = {}
        
        for course in schedule['courses']:
            teacher = course['teacher_code']
            credit = self.courses[course['course_code']][3]  # credit hours
            
            if teacher in teacher_load:
                teacher_load[teacher] += credit
            else:
                teacher_load[teacher] = credit
        
        for teacher, load in teacher_load.items():
            min_duty = self.teachers[teacher][5]
            max_duty = self.teachers[teacher][4]
            
            if load < min_duty or load > max_duty:
                issues += 1
        
        return issues
    
    def check_room_capacity(self, schedule):
        """Check if room capacity meets course requirements"""
        issues = 0
        
        for course in schedule['courses']:
            place_code = course['place_code']
            expected_capacity = self.courses[course['course_code']].get('expected_students', 30)
            room_capacity = self.places[place_code][2]
            
            if room_capacity < expected_capacity:
                issues += 1
        
        return issues
    
    def feasible_function(self, population):
        """Ensure all schedules meet basic constraints"""
        for schedule in population:
            # Ensure gender compatibility
            for course in schedule['courses']:
                teacher_sex = self.teachers[course['teacher_code']][7]
                course_sex = self.courses[course['course_code']][8]
                place_sex = self.places[course['place_code']][3]
                
                # Check teacher-course gender compatibility
                if course_sex != 0 and teacher_sex != course_sex:
                    # Find a compatible teacher
                    compatible_teachers = [
                        t for t in self.teachers.values() 
                        if t[7] == course_sex and course['course_code'] in t[8]
                    ]
                    
                    if compatible_teachers:
                        course['teacher_code'] = random.choice(compatible_teachers)[0]
                
                # Check place-course gender compatibility
                if course_sex != 0 and place_sex != 0 and place_sex != course_sex:
                    # Find a compatible place
                    compatible_places = [
                        p for p in self.places.values() 
                        if p[3] == course_sex or p[3] == 0
                    ]
                    
                    if compatible_places:
                        course['place_code'] = random.choice(compatible_places)[0]
        
        return population
    
    def initialize_population(self):
        """Create initial population of random schedules"""
        population = []
        
        for _ in range(self.OPTIONS['popsize']):
            schedule = {'courses': []}
            
            # For each course, randomly assign teacher, place and time slot
            for course_code, course_info in self.courses.items():
                # Find compatible teachers
                compatible_teachers = [
                    t[0] for t in self.teachers.values() 
                    if course_code in t[8] and (
                        course_info[8] == 0 or t[7] == course_info[8]
                    )
                ]
                
                if not compatible_teachers:
                    continue
                
                # Find compatible places
                compatible_places = [
                    p[0] for p in self.places.values() 
                    if (course_info[8] == 0 or p[3] == 0 or p[3] == course_info[8]) and
                    p[4] == 1  # available
                ]
                
                if not compatible_places:
                    continue
                
                # Randomly select teacher, place and time slot
                teacher = random.choice(compatible_teachers)
                place = random.choice(compatible_places)
                slot = random.choice(list(self.time_slots.keys()))
                
                schedule['courses'].append({
                    'course_code': course_code,
                    'teacher_code': teacher,
                    'place_code': place,
                    'slot_id': slot
                })
            
            population.append(schedule)
        
        return population
    
    def run_bbo(self):
        """Run BBO algorithm to find optimal schedule"""
        # Initialize population
        population = self.initialize_population()
        
        # Evaluate initial population
        population = self.cost_function(population)
        population = sorted(population, key=lambda x: x['cost'])
        
        best_schedule = population[0]
        best_cost = best_schedule['cost']
        
        for gen in range(self.OPTIONS['maxgen']):
            # Keep elite solutions
            elites = population[:self.OPTIONS['keep']]
            
            # Get species counts
            population = self.get_species_counts(population)
            
            # Get immigration and emigration rates
            lambda_rates, mu_rates = self.get_lambda_mu(population)
            
            # Migration
            for i, schedule in enumerate(population):
                if random.random() > self.OPTIONS['pmodify']:
                    continue
                
                # Normalize immigration rate
                lambda_min = min(lambda_rates)
                lambda_max = max(lambda_rates)
                lambda_scale = self.OPTIONS['lamdalower'] + (
                    self.OPTIONS['lamdaupper'] - self.OPTIONS['lamdalower']
                ) * (lambda_rates[i] - lambda_min) / (lambda_max - lambda_min)
                
                # Probabilistically migrate features
                for j in range(len(schedule['courses'])):
                    if random.random() < lambda_scale:
                        # Roulette wheel selection based on emigration rates
                        rand_num = random.random() * sum(mu_rates)
                        select_index = 0
                        select_sum = mu_rates[0]
                        
                        while rand_num > select_sum and select_index < len(population)-1:
                            select_index += 1
                            select_sum += mu_rates[select_index]
                        
                        # Migrate this course assignment
                        schedule['courses'][j] = population[select_index]['courses'][j]
            
            # Mutation
            population = sorted(population, key=lambda x: x['cost'])
            half = len(population) // 2
            
            for i in range(half, len(population)):
                for j in range(len(population[i]['courses'])):
                    if random.random() < self.OPTIONS['pmutate']:
                        # Mutate this course assignment
                        course = population[i]['courses'][j]
                        
                        # Mutate teacher
                        compatible_teachers = [
                            t[0] for t in self.teachers.values() 
                            if course['course_code'] in t[8] and (
                                self.courses[course['course_code']][8] == 0 or 
                                t[7] == self.courses[course['course_code']][8]
                            )
                        ]
                        if compatible_teachers:
                            course['teacher_code'] = random.choice(compatible_teachers)
                        
                        # Mutate place
                        compatible_places = [
                            p[0] for p in self.places.values() 
                            if (self.courses[course['course_code']][8] == 0 or 
                                p[3] == 0 or 
                                p[3] == self.courses[course['course_code']][8]) and
                            p[4] == 1
                        ]
                        if compatible_places:
                            course['place_code'] = random.choice(compatible_places)
                        
                        # Mutate time slot
                        course['slot_id'] = random.choice(list(self.time_slots.keys()))
            
            # Ensure feasibility
            population = self.feasible_function(population)
            
            # Evaluate new population
            population = self.cost_function(population)
            population = sorted(population, key=lambda x: x['cost'])
            
            # Replace worst solutions with elites
            for i in range(self.OPTIONS['keep']):
                population[-(i+1)] = elites[i]
            
            # Update best solution
            if population[0]['cost'] < best_cost:
                best_schedule = population[0]
                best_cost = best_schedule['cost']
            
            print(f"Generation {gen}: Best Cost = {best_cost}")
        
        return best_schedule

    def get_species_counts(self, population):
        """Map cost values to species counts"""
        p = len(population)
        for i, h in enumerate(population):
            h['SpeciesCount'] = p - i
        return population
    
    def get_lambda_mu(self, population, I=1, E=1):
        """Compute immigration and emigration rates"""
        P = len(population)
        lambda_rates = [I * (1 - (h['SpeciesCount'] / P)) for h in population]
        mu_rates = [E * (h['SpeciesCount'] / P) for h in population]
        return lambda_rates, mu_rates

    def save_schedule_to_db(self, schedule):
        """Save the best schedule to database"""
        cur = self.conn.cursor()
        
        # Clear existing schedule
        cur.execute("TRUNCATE TABLE schedule")
        
        # Insert new schedule
        for course in schedule['courses']:
            cur.execute(
                "INSERT INTO schedule (course_code, teacher_code, place_code, slot_id) VALUES (%s, %s, %s, %s)",
                (course['course_code'], course['teacher_code'], course['place_code'], course['slot_id'])
            )
        
        self.conn.commit()
        cur.close()

# Run the algorithm
if __name__ == "__main__":
    problem = CourseSchedulingProblem("config.yaml")
    best_schedule = problem.run_bbo()
    problem.save_schedule_to_db(best_schedule)
    
    print("Best schedule found with cost:", best_schedule['cost'])
    for course in best_schedule['courses']:
        print(f"Course: {course['course_code']}, Teacher: {course['teacher_code']}, Place: {course['place_code']}, Time: {problem.time_slots[course['slot_id']][1]}")