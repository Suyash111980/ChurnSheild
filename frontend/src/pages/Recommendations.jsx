
          const learner = item.learner || {};
          const learnerLabel =
            learner.external_learner_id ??
            item.external_learner_id ??
            item.id_student ??
            item.learner_id;

          const courseLabel = [
            learner.code_module || item.code_module,
            learner.code_presentation || item.code_presentation,
          ]
            .filter(Boolean)
            .join(" · ");

          const presentation = formatRecommendation(item);
          const prediction = item.prediction || {};

          const risk =
            prediction.risk_category ||
            presentation.risk ||
            item.risk_category;

          const probability =
            typeof prediction.risk_probability === "number"
              ? prediction.risk_probability
              : presentation.probability;

          const modelVersion =
            prediction.model_version || presentation.modelVersion;

          const hasRisk = ["low", "medium", "high"].includes(
            String(risk || "").toLowerCase()
          );

          const formattedProbability =
            typeof probability === "number" &&
            Number.isFinite(probability) &&
            probability >= 0 &&
            probability <= 1
              ? `${(probability * 100).toFixed(1)}%`
              : null;

          return (
            <article className="action-row" key={item.id}>
              <i className={`action-edge ${riskName(risk)}`} />

              <div className="action-copy recommendation-copy">
                <strong>
                  {presentation.title || item.action || "Recommendation"}
                </strong>

                <section>
                  <small>Observed reason</small>
                  <span>
                    {presentation.reason ||
                      item.reason ||
                      "No supporting rationale was recorded."}
                  </span>
                </section>

                <section>
                  <small>Suggested action</small>
                  <span>
                    {presentation.action || item.action || "Review this recommendation"}
                  </span>
                </section>

                {learnerLabel && (
                  <small className="action-context">
                    Learner {learnerLabel}
                    {courseLabel ? ` · ${courseLabel}` : ""}
                  </small>
                )}

                <div className="recommendation-context">
                  <span className={`recommendation-priority ${riskName(risk)}`}>
                    Priority: {presentation.priority || "Review"}
                  </span>

                  {hasRisk && (
                    <span className={`risk-badge ${riskName(risk)}`}>
                      {risk} risk
                    </span>
                  )}

                  {formattedProbability && (
                    <span>
                      {formattedProbability} persisted risk probability
                    </span>
                  )}

                  {modelVersion && <span>Model {modelVersion}</span>}
                </div>

                {(presentation.technicalReason ||
                  presentation.ruleId ||
                  item.rule_id ||
                  item.prediction_id) && (
                  <details className="recommendation-evidence">
                    <summary>Recorded technical evidence</summary>
                    <dl>
                      {(presentation.technicalReason || presentation.ruleId || item.rule_id) && (
                        <div>
                          <dt>Rule / evidence</dt>
                          <dd>
                            {presentation.technicalReason ||
                              presentation.ruleId ||
                              item.rule_id}
                          </dd>
                        </div>
                      )}
                      <div>
                        <dt>Prediction</dt>
                        <dd>{item.prediction_id || "Not linked"}</dd>
                      </div>
                      <div>
                        <dt>Review</dt>
                        <dd>
                          Human review required; this suggestion is advisory.
                        </dd>
                      </div>
                    </dl>
                  </details>
                )}

                {!hasRisk && item.prediction_id && (
                  <small className="action-context">
                    Prediction risk context unavailable
                  </small>
                )}
              </div>
