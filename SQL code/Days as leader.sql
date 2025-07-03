WITH DailyUserTotals AS (
    SELECT
        u.user_name,
        c.Date_Complete,
        COUNT(*) AS total
    FROM Chore_Assignments AS c
    INNER JOIN Users AS u ON u.user_id = c.Completed_By
    WHERE c.Completion_Status = 'complete' and u.family_id = 1
    GROUP BY u.user_name, c.Date_Complete
),
DailyLeaders AS (
    SELECT *,
           RANK() OVER (PARTITION BY Date_Complete ORDER BY total DESC) AS rk
    FROM DailyUserTotals
)
SELECT top 1
    user_name,
    COUNT(*) AS days_as_leader
FROM DailyLeaders
WHERE rk = 1
GROUP BY user_name
ORDER BY days_as_leader DESC;