INSERT INTO Chore_Assignments (
    Chore_ID,
    Assigned_To,
    Assigned_By,
    Date_Assigned,
    Completion_Status
)
VALUES (
    1,      -- Chore_ID
    1,      -- Assigned_To
    1,      -- Assigned_By (your wife probably)
    GETDATE(),
    'Pending'
);