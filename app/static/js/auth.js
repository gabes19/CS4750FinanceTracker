document.addEventListener("DOMContentLoaded", () => {
  const emailField =
    document.getElementById("login-email") ||
    document.getElementById("register-email");
  emailField?.focus();
});
