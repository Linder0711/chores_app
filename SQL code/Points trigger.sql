CREATE TRIGGER trg_AwardPointsOnCompletion
ON Chore_Assignments
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE CA
    SET Points_Earned = 1
    FROM Chore_Assignments AS CA
    INNER JOIN inserted AS i ON CA.Assignment_ID = i.Assignment_ID
    WHERE i.Completion_Status = 'Complete';
END;
