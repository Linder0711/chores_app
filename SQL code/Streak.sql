WITH Streaktotal AS (
SELECT
        u.user_name,
        c.Date_Complete,
        ROW_NUMBER() OVER (PARTITION BY u.user_name order by u.user_name,c.Date_Complete asc ) AS rn,
		datediff(day,'05-24-2025',c.Date_Complete) as num,
		datediff(day,'05-24-2025',c.Date_Complete) - ROW_NUMBER() OVER (PARTITION BY u.user_name order by u.user_name,c.Date_Complete asc )as diff
    FROM Chore_Assignments AS c
    INNER JOIN Users AS u ON u.user_id = c.Completed_By
    WHERE c.Completion_Status = 'complete' and u.family_id = 1
    GROUP BY u.user_name, c.Date_Complete)

Select top 1
User_name, COUNT(*) as total from Streaktotal
Group by user_name, diff
order by total desc
