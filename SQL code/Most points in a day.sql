Select Top 1 u.User_name, Sum(c.Points_earned)as points, c.Date_Complete
From Chore_assignments as c
Inner join users as u
on c.Completed_By = u.User_ID
Group by u.user_name, c.Date_Complete
Order by points desc
