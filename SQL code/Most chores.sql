Select top 1 u.user_name, COUNT (distinct cl.Chore_name) as total
From Chore_Assignments as ca
Inner Join users as u on
ca.Completed_By = u.User_ID
Inner Join Chores_list as cl
on ca.Chore_ID = cl.chore_id
where ca.Completion_Status = 'complete' and cl.Family_id in (1,2)
Group by u.user_name
order by total desc