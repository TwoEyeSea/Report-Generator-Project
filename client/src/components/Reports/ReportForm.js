import React from "react";
import { connect } from "react-redux";
import { Field, Form } from "react-final-form";
import arrayMutators from "final-form-arrays";
import { FieldArray } from "react-final-form-arrays";
import { fetchUnits } from "../../actions";
import { Link } from "react-router-dom";
import DropdownExample from "../semantic-ui-components/dropdown";
import _ from "lodash";

import "../form.css";

class ReportForm extends React.Component {
  componentDidMount() {
    this.props.fetchUnits();
  }

  // Error Validation for the input fields, if the input field becomes touched but is left empty the component throws an error.
  renderError = ({ error, touched }) => {
    if (touched && error) {
      return (
        <div className="ui error message">
          <div className="header">{error}</div>
        </div>
      );
    }
  };

  //INPUT FIELD HELPER FUNCTION

  renderInput = ({ input, label, meta }) => {
    // The renderInput helper method is used to pass JSX to the Field element from react-final-form library
    // We can destructure the "input" property from the formProps.input and call it as a prop within the <input /> element as shown below.
    const className = `field ${meta.error && meta.touched ? "error" : ""}`;

    return (
      <div className={className}>
        <label>{label}</label>
        {/* The label prop is destructured within the renderInput Function and placed within the <label> element   */}
        <input {...input} autoComplete="off" />
        {this.renderError(meta)}
      </div>
    );
  };

  // Helper function to extract values from the dropdown component
  // handledropdown is invoked via the onChange function within the dropdown component and is asynchronous, in order to get updated state from it we need to pass it a callback function.

  handleDropdown = (event, data) => {
    this.setState(
      {
        [data.name]: data.value,
      },
      () => {
        console.log(this.props.units);
      }
    );
  };

  onSubmit = (formValues) => {
    this.props.onSubmit(formValues);
    // The ReportForm component will receive an onSubmmit function from its parent component as a prop.
  };

  render() {
    return (
      <Form // Important note, the name for the form fields need to be identical to the terms in the schema for data to be posted properly. The field names need to be === to the names defined in validation as well.
        initialValues={this.props.initialValues}
        onSubmit={this.onSubmit}
        mutators={{
          ...arrayMutators,
        }}
        validate={(formValues) => {
          const errors = {};

          if (!formValues.reportId) {
            errors.reportId = "You must enter a report number";
            // CONSIDER - Since i'll have many input fields it may be more efficient to pass the "name" of each input field programatically instead of hard coding each error type. using an or statement or switch and case to cycle through input field titles.
          }

          if (!formValues.clientName) {
            errors.clientName = "You must enter a client name";
          }

          return errors;
        }}
        render={({
          handleSubmit,
          form: {
            mutators: { push, pop },
          },
          pristine,
          form,
          submitting,
          values,
        }) => (
          <form onSubmit={handleSubmit} className="ui form error">
            <Field
              name="reportId"
              component={this.renderInput}
              label={"Enter Report Number (as number)"}
            />
            <Field
              name="clientName"
              component={this.renderInput}
              label={"Enter Client Name"}
            />
            <Field
              name="block"
              component={this.renderInput}
              label={"Enter Site Location Block"}
            />
            <Field
              name="parcel"
              component={this.renderInput}
              label={"Enter Site Location Parcel"}
            />
            <Field
              name="siteAddress"
              component={this.renderInput}
              label={"Enter Site Address"}
            />
            <Field
              name="investigationDate"
              component={this.renderInput}
              label={"Enter Date of Investigation"}
            />
            <Field
              name="engineerAMR"
              component={this.renderInput}
              label={"Enter Engineers Present"}
            />
            <Field
              name="weather"
              component={this.renderInput}
              label={"Enter Weather Conditions During Investigation"}
            />
            <Field
              name="investigationDuration"
              component={this.renderInput}
              label={"Enter Duration of Investigation"}
            />
            <Field
              name="trialPitNumber"
              component={this.renderInput}
              label={"Enter Number of Trial Pits Excavated"}
            />

            <div>
              <button
                className="small ui button brown"
                type="button"
                onClick={() => push("unitDescriptions", undefined)}
              >
                Create Custom Unit Description
              </button>
              <button
                className="small ui button brown"
                type="button"
                onClick={() => push("unitDescriptions", this.props.units[0])}
              >
                another
              </button>
              <button
                className="small ui button brown"
                type="button"
                onClick={() => pop("unitDescriptions")}
              >
                Remove Remove a Unit Description
              </button>
            </div>

            <FieldArray name="unitDescriptions">
              {({ fields }) =>
                fields.map((name, index) => (
                  <div key={`tp ${index + 1}`} className="fieldArrayDiv">
                    <label>Unit Description #{index + 1}</label>{" "}
                    {/*Incrementing the customer#*/}
                    <div className="field">
                      <Field
                        name={`${name}.strata`}
                        component="input"
                        placeholder="Define the Stratum / Subsurface Unit."
                      />
                    </div>
                    <div className="field">
                      <Field
                        name={`${name}.numberOfTrialPits`}
                        component="input"
                        placeholder="Trial pits where this unit was encountered (e.g. 1, 2, 3)."
                      />
                    </div>
                    <div className="field">
                      <Field
                        name={`${name}.thicknessRange`}
                        component="input"
                        placeholder='State the thickness range of this unit". '
                      />
                    </div>
                    <div className="field">
                      <Field
                        name={`${name}.underlying`}
                        component="input"
                        placeholder='State which unit this unit underlies or state "On grade". '
                      />
                    </div>
                    <div className="field">
                      <Field
                        name={`${name}.description`}
                        component="textarea"
                        placeholder="Provide a description for the unit."
                      />
                    </div>
                    <div className="ui right floated large basic icon buttons">
                      <button
                        type="button"
                        className="ui button space"
                        onClick={() => fields.remove(index)}
                        style={{ curson: "pointer" }}
                      >
                        <i className="trash alternate icon"></i>
                      </button>
                    </div>
                  </div>
                ))
              }
            </FieldArray>
            <div className="ui divider"></div>

            <div>
              <button
                className="small ui button orange"
                type="button"
                onClick={() => push("trialPits", undefined)}
              >
                Add Trial Pit
              </button>
              <button
                className="small ui button orange"
                type="button"
                onClick={() => pop("trialPits")}
              >
                Remove Trial Pit
              </button>
            </div>

            <div className="section">
              <FieldArray name="trialPits">
                {({ fields }) =>
                  fields.map((name, index) => (
                    <div key={`tp ${index + 1}`} className="fieldArrayDiv">
                      <label>Trial Pit#{index + 1}</label>{" "}
                      {/*Incrementing the customer#*/}
                      <div className="field">
                        <Field
                          name={`${name}.groundWaterLevel`}
                          component="input"
                          placeholder="Recharged ground water level (in inches or undefined)"
                        />
                      </div>
                      <div className="field">
                        <Field
                          name={`${name}.finalDepth`}
                          component="input"
                          placeholder="Final depth of trial pit"
                        />
                      </div>
                      <div className="field">
                        <Field
                          name={`${name}.bearingStratum`}
                          component="input"
                          placeholder="State competent stratum if encountered"
                        />
                      </div>
                      <div className="ui right floated large basic icon buttons">
                        <button
                          type="button"
                          className="ui button space"
                          onClick={() => fields.remove(index)}
                          style={{ curson: "pointer" }}
                        >
                          <i className="trash alternate icon"></i>
                        </button>
                      </div>
                    </div>
                  ))
                }
              </FieldArray>
              <div className="ui divider"></div>
            </div>

            <button className="ui button primary">Submit</button>
            <pre>{JSON.stringify(values, 0, 2)}</pre>
          </form>
        )}
      />
    );
  }
}
const mapStateToProps = (state) => {
  return {
    units: Object.values(state.units),
  };
};

export default connect(mapStateToProps, { fetchUnits })(ReportForm);

// // Helper function to add input fields for unit descriptions
// const mapUnitDescriptionInputs() {
//   return props.units.units.map((item) => {
//     return <Field name={`${item}`} component={this.renderInput} label={"Enter Unit"} />;
//   });
// }

// Helper function to initiate action creaor to add another unit
// const addNewUnit() {
//   console.log(this.state.unitId);
//   this.setState({ unitId: this.state.unitId + 1 });
//   return this.props.addUnit(this.state.unitId);
// }
