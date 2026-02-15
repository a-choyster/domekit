# Health PoC — Test Questions

Run each question against the running DomeKit runtime:

```bash
python apps/health-poc/client/health.py ask "<question>"
```

## Questions

### 1. Activity count
**Q:** "How many activities did I log in the last 30 days?"
**Expected tool:** `sql_query` — `SELECT COUNT(*) FROM activities WHERE date >= date('now', '-30 days')`
**Expected behavior:** Returns a numeric count.

### 2. Average resting heart rate
**Q:** "What's my average resting heart rate?"
**Expected tool:** `sql_query` — `SELECT AVG(resting_hr) FROM daily_metrics`
**Expected behavior:** Returns a number between ~55–75.

### 3. Best running distance
**Q:** "What was my longest running distance?"
**Expected tool:** `sql_query` — `SELECT MAX(distance_km) FROM activities WHERE type = 'running'`
**Expected behavior:** Returns a distance in km.

### 4. Sleep patterns
**Q:** "How are my sleep patterns over the last two weeks?"
**Expected tool:** `sql_query` — queries `sleep_hours` from `daily_metrics` for recent dates
**Expected behavior:** Summarizes average/trend in sleep hours.

### 5. Weekly step trends
**Q:** "Show my weekly step totals for the last month."
**Expected tool:** `sql_query` — aggregates `steps` by week from `daily_metrics`
**Expected behavior:** Returns weekly totals or averages.

### 6. Calorie summary by activity type
**Q:** "How many total calories did I burn per activity type?"
**Expected tool:** `sql_query` — `SELECT type, SUM(calories) FROM activities GROUP BY type`
**Expected behavior:** Breakdown by running, cycling, walking, swimming.

### 7. Most active day
**Q:** "Which day did I have the most active minutes?"
**Expected tool:** `sql_query` — `SELECT date, active_minutes FROM daily_metrics ORDER BY active_minutes DESC LIMIT 1`
**Expected behavior:** Returns a specific date and minute count.

### 8. Swimming frequency
**Q:** "How often did I go swimming?"
**Expected tool:** `sql_query` — `SELECT COUNT(*) FROM activities WHERE type = 'swimming'`
**Expected behavior:** Returns a count.

### 9. Heart rate during cycling
**Q:** "What's my average heart rate during cycling sessions?"
**Expected tool:** `sql_query` — `SELECT AVG(avg_hr) FROM activities WHERE type = 'cycling'`
**Expected behavior:** Returns a number between ~110–160.

### 10. Stress vs sleep correlation
**Q:** "Is there a relationship between my stress score and sleep hours?"
**Expected tool:** `sql_query` — queries both columns, possibly ordered or averaged
**Expected behavior:** The model describes any observed pattern.

### 11. Recent activity log
**Q:** "Show me my last 5 activities."
**Expected tool:** `sql_query` — `SELECT * FROM activities ORDER BY date DESC LIMIT 5`
**Expected behavior:** Lists the 5 most recent activities with details.

### 12. Low sleep days
**Q:** "On how many days did I sleep less than 6 hours?"
**Expected tool:** `sql_query` — `SELECT COUNT(*) FROM daily_metrics WHERE sleep_hours < 6`
**Expected behavior:** Returns a count.
