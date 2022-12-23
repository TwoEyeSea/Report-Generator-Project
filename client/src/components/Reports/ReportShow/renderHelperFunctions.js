import React from "react";

const renderUnitDescription = (unitBlock) => {
  return unitBlock.map((unit) => {
    return (
      <div key={unit.strata}>
        <p
          className={21}
          align="left"
          style={{
            marginLeft: "42.55pt",
            textAlign: "left",
            textIndent: "0in",
          }}
        >
          <b>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              Strata:{" "}
            </span>
          </b>
          <span
            style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
          >
            {unit.strata}
          </span>
        </p>
        <p
          className={21}
          align="left"
          style={{
            marginLeft: "42.55pt",
            textAlign: "left",
            textIndent: "0in",
          }}
        >
          <b>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              Trial pit No. encountered:{" "}
            </span>
          </b>
          <span
            style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
          >
            {unit.numberOfTrialPits}
          </span>
        </p>
        <p
          className={21}
          align="left"
          style={{
            marginLeft: "42.55pt",
            textAlign: "left",
            textIndent: "0in",
          }}
        >
          <b>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              Thickness range:{" "}
            </span>
          </b>
          <span
            style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
          >
            {unit.thicknessRange}
          </span>
        </p>
        <p
          className={21}
          align="left"
          style={{
            marginLeft: "42.55pt",
            textAlign: "left",
            textIndent: "0in",
          }}
        >
          <b>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              Underlying:
            </span>
          </b>
          <span
            style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
          >
            {unit.underlying}
          </span>
        </p>
        <p
          className="Legal2"
          style={{ marginLeft: "42.55pt", textIndent: "0in" }}
        >
          <b>
            <span
              style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
            >
              Description:
            </span>
          </b>
          <span
            style={{
              overflow: "visible",
              whiteSpace: "pre-wrap",
              overflowWrap: "break-word",
              fontSize: "11.0pt",
              fontFamily: '"Arial",sans-serif',
            }}
          >
            {" "}
            {unit.description}
          </span>
        </p>
        <p
          className={21}
          align="left"
          style={{ marginLeft: "0in", textAlign: "left", textIndent: "0in" }}
        >
          <span
            style={{ fontSize: "11.0pt", fontFamily: '"Arial",sans-serif' }}
          >
            &nbsp;
          </span>
        </p>
      </div>
    );
  });
};

export default renderUnitDescription;
