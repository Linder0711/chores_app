CREATE TRIGGER trg_updatechoreassignmentsingle
ON dbo.Chore_Assignments
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    -- ✅ Award points
    UPDATE CA
    SET Points_Earned = 1
    FROM Chore_Assignments AS CA
    INNER JOIN inserted AS i ON CA.Assignment_ID = i.Assignment_ID
    INNER JOIN deleted AS d ON d.Assignment_ID = i.Assignment_ID
    WHERE i.Completion_Status = 'Complete'
      AND d.Completion_Status <> 'Complete'
      AND CA.Points_Earned = 0;

    -- ✅ Insert into User_Points
    INSERT INTO User_Points (User_ID, Assignment_ID, Points, Date_Awarded)
    SELECT 
        i.Completed_By,
        i.Assignment_ID,
        1,
        GETDATE()
    FROM inserted i
    INNER JOIN deleted d ON d.Assignment_ID = i.Assignment_ID
    WHERE i.Completion_Status = 'Complete'
      AND d.Completion_Status <> 'Complete';

    -- ✅ Log audit of chore completion
    INSERT INTO App_Audit_Log (
        user_id,
        action_type,
        target_table,
        target_id,
        details
    )
    SELECT 
        i.completed_by,
        'complete_chore',
        'Chore_Assignments',
        i.assignment_id,
        CONCAT('{"assigned_to":', i.assigned_to, 
               ', "chore_id":', i.chore_id, 
               ', "date_complete":"', FORMAT(i.date_complete, 'yyyy-MM-dd HH:mm:ss'), '"}')
    FROM inserted i
    INNER JOIN deleted d ON d.Assignment_ID = i.Assignment_ID
    WHERE i.Completion_Status = 'Complete'
      AND d.Completion_Status <> 'Complete';

    -- ✅ Update the timestamp
    -- Only run if any value actually changed
    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN deleted d ON i.Assignment_ID = d.Assignment_ID
        WHERE 
            ISNULL(i.Completion_Status, '') <> ISNULL(d.Completion_Status, '')
            OR ISNULL(i.Points_Earned, -1) <> ISNULL(d.Points_Earned, -1)
            OR ISNULL(i.Date_Complete, '') <> ISNULL(d.Date_Complete, '')
            OR ISNULL(i.Completed_By, -1) <> ISNULL(d.Completed_By, -1)
    )
    BEGIN
        UPDATE CA
        SET Updated_At = GETDATE()
        FROM Chore_Assignments AS CA
        INNER JOIN inserted AS i ON CA.Assignment_ID = i.Assignment_ID;
    END
END;