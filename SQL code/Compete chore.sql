UPDATE Chore_Assignments
SET Completion_Status = 'Complete',
    Date_Complete = GETDATE(),
    Completed_By = 1
WHERE Assignment_ID = 6;
