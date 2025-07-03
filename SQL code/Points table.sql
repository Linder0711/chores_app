Use Chores
CREATE TABLE User_Points (
    Point_ID INT IDENTITY(1,1) PRIMARY KEY,
    User_ID INT NOT NULL,
    Assignment_ID INT NOT NULL,
    Points INT DEFAULT 1,
    Date_Awarded DATETIME DEFAULT GETDATE(),

    FOREIGN KEY (User_ID) REFERENCES Users(user_id),
    FOREIGN KEY (Assignment_ID) REFERENCES Chore_Assignments(Assignment_ID)
);
