DECLARE @cols NVARCHAR(MAX), @query NVARCHAR(MAX);

-- Step 1: Get column headers (one per date)
SELECT @cols = STRING_AGG(QUOTENAME(date_complete), ',') WITHIN GROUP (ORDER BY date_complete)
FROM (
    SELECT DISTINCT CONVERT(varchar(10), Date_name, 120) AS date_complete
    FROM Date_list
    WHERE date_name >= DATEADD(DAY, -30, GETDATE())
	and date_name <= GETDATE()
) AS date_list;

-- Step 2: Construct the dynamic SQL string
SET @query = '
SELECT user_name, ' + @cols + '
FROM (
    SELECT 
        u.user_name,
        CONVERT(varchar(10), ca.date_complete, 120) AS date_only,
        1 AS chore_count
    FROM chore_assignments ca
    INNER JOIN users u ON ca.completed_by = u.user_id
    WHERE ca.completion_status = ''complete''
      AND u.family_id = 1
      AND u.role_id <> 4
      AND ca.date_complete >= DATEADD(DAY, -30, GETDATE())
) AS src
PIVOT (
    COUNT(chore_count)
    FOR date_only IN (' + @cols + ')
) AS pvt
ORDER BY user_name;
';

-- Step 3: Execute the dynamic SQL
EXEC sp_executesql @query;
