import React from "react";
import { Dropdown } from "semantic-ui-react";

const options = [
  { key: 1, text: "Peat", value: "Peat" },
  { key: 2, text: "Choice 2", value: 2 },
  { key: 3, text: "Choice 3", value: 3 },
];

const DropdownExample = (props) => (
  <Dropdown
    name="unitDescription"
    placeholder="Select a Template Unit Description"
    options={options}
    onChange={props.handleDropdown}
    selection
  />
);

export default DropdownExample;
