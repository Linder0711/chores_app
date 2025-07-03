Use Chores
CREATE TABLE Chore_Assignments (
    Assignment_ID INT IDENTITY(1,1) PRIMARY KEY,
    Chore_ID INT NOT NULL,
    Assigned_To INT NOT NULL,
    Assigned_By INT NOT NULL,
    Date_Assigned DATE NOT NULL,
    Completion_Status VARCHAR(20) DEFAULT 'Pending',
    Date_Complete DATE,
    Completed_By INT,
    Created_At DATETIME DEFAULT GETDATE(),
    Updated_At DATETIME DEFAULT GETDATE(),

    FOREIGN KEY (Chore_ID) REFERENCES Chores_list(Chore_id),
    FOREIGN KEY (Assigned_To) REFERENCES Users(user_id),
    FOREIGN KEY (Assigned_By) REFERENCES Users(user_id),
    FOREIGN KEY (Completed_By) REFERENCES Users(user_id)
);
