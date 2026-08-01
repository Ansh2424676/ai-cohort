# Structured SQL Queries

## Query 1
### Question
What is the deductible on the Gold PPO plan?

```sql
SELECT annual_deductible
FROM plans
WHERE plan_name='Gold PPO';
```

Output

2000

---

## Query 2

### Question

How many claims are pending for member M1001?

```sql
SELECT COUNT(*)
FROM claims
WHERE member_id='M1001'
AND status='Pending';
```

Output

1

---

## Query 3

### Question

Which plans have a monthly premium under $400?

```sql
SELECT plan_name, monthly_premium
FROM plans
WHERE monthly_premium<400;
```

Output

Silver HMO
Bronze HMO

---

## Query 4

### Question

Join plans and claims

```sql
SELECT member_id,
plan_name,
claim_amount,
status
FROM claims
JOIN plans
ON claims.plan_id=plans.plan_id;
```

Output

5 rows returned

---

## Query 5

### Question

Most claimed procedures

```sql
SELECT procedure,
COUNT(*) AS total
FROM claims
GROUP BY procedure
ORDER BY total DESC;
```

Output

X-ray : 3

Surgery : 2