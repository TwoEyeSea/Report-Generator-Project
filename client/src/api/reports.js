import axios from "axios";

export default axios.create({
  baseURL: "http://localhost:8080/api",
  // We can hide the port in a .env file
});
