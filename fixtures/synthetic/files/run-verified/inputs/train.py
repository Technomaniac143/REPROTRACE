import data

model = fit(data.train)
save(evaluate(model, data.test))
