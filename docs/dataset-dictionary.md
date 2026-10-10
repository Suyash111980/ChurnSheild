# Dataset notes

The planned source is OULAD. Keep original files in `ml/data/raw/` locally and generated features in `ml/data/processed/`; both are ignored by Git. Learner-course identity is `(id_student, code_module, code_presentation)`. Store engineered values with an `as_of_date`. Never use `final_result` as a feature. Add exact feature names once the ML team agrees on the inference schema.
