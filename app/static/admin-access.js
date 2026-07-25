(() => {
  "use strict";

  const onReady = (callback) => {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback);
    } else {
      callback();
    }
  };

  const setChecked = (checkboxes, checked) => {
    checkboxes.forEach((checkbox) => {
      checkbox.checked = checked;
      checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    });
  };

  onReady(() => {
    document.querySelectorAll("form[data-confirm]").forEach((form) => {
      form.addEventListener("submit", (event) => {
        if (!window.confirm(form.dataset.confirm || "Continue?")) {
          event.preventDefault();
        }
      });
    });
    document.querySelectorAll("button[data-confirm]").forEach((button) => {
      button.addEventListener("click", (event) => {
        if (!window.confirm(button.dataset.confirm || "Continue?")) {
          event.preventDefault();
        }
      });
    });

    document.querySelectorAll("[data-permission-editor]").forEach((editor) => {
      const checkboxes = Array.from(
        editor.querySelectorAll('input[name="permissions"]')
      );
      const updateCount = () => {
        const count = checkboxes.filter((checkbox) => checkbox.checked).length;
        editor.querySelectorAll("[data-permission-count]").forEach((node) => {
          node.textContent = String(count);
        });
      };
      checkboxes.forEach((checkbox) =>
        checkbox.addEventListener("change", updateCount)
      );
      updateCount();

      editor
        .querySelector('[data-permission-action="clear"]')
        ?.addEventListener("click", () => setChecked(checkboxes, false));
      editor
        .querySelector('[data-permission-action="read"]')
        ?.addEventListener("click", () => {
          setChecked(
            checkboxes.filter(
              (checkbox) =>
                checkbox.value.endsWith(".read") ||
                checkbox.value.endsWith(".view")
            ),
            true
          );
        });
      editor
        .querySelector('[data-permission-action="expand"]')
        ?.addEventListener("click", () => {
          editor
            .querySelectorAll("[data-permission-group]")
            .forEach((group) => {
              group.open = true;
            });
        });
      editor
        .querySelector('[data-permission-action="collapse"]')
        ?.addEventListener("click", () => {
          editor
            .querySelectorAll("[data-permission-group]")
            .forEach((group) => {
              group.open = false;
            });
        });

      editor.querySelectorAll("[data-permission-group]").forEach((group) => {
        const groupCheckboxes = Array.from(
          group.querySelectorAll('input[name="permissions"]')
        );
        group
          .querySelector("[data-permission-group-select]")
          ?.addEventListener("click", (event) => {
            event.preventDefault();
            setChecked(groupCheckboxes, true);
          });
        group
          .querySelector("[data-permission-group-clear]")
          ?.addEventListener("click", (event) => {
            event.preventDefault();
            setChecked(groupCheckboxes, false);
          });
      });

      editor
        .querySelector("[data-permission-search]")
        ?.addEventListener("input", (event) => {
          const query = event.target.value.trim().toLowerCase();
          editor.querySelectorAll("[data-permission-option]").forEach((option) => {
            const matches =
              !query ||
              (option.dataset.permissionSearchValue || "")
                .toLowerCase()
                .includes(query);
            option.hidden = !matches;
            if (matches && query) {
              option.closest("[data-permission-group]").open = true;
            }
          });
        });
    });

    document.querySelectorAll("[data-role-editor]").forEach((editor) => {
      const cards = Array.from(editor.querySelectorAll("[data-role-card]"));
      const checkboxes = cards
        .map((card) => card.querySelector('input[name="roles"]'))
        .filter(Boolean);
      const updateRoleSummary = () => {
        const selectedCards = cards.filter(
          (card) => card.querySelector('input[name="roles"]')?.checked
        );
        const permissions = new Set();
        selectedCards.forEach((card) => {
          try {
            JSON.parse(card.dataset.rolePermissions || "[]").forEach(
              (permission) => permissions.add(permission)
            );
          } catch (_error) {
            // The preview is informational; malformed metadata never grants access.
          }
        });
        editor.querySelectorAll("[data-selected-role-count]").forEach((node) => {
          node.textContent = String(selectedCards.length);
        });
        editor
          .querySelectorAll("[data-selected-permission-count]")
          .forEach((node) => {
            node.textContent = String(permissions.size);
          });
        const union = editor.querySelector("[data-permission-union]");
        if (union) {
          union.replaceChildren(
            ...Array.from(permissions)
              .sort()
              .map((permission) => {
                const badge = document.createElement("code");
                badge.className = "tm-permission-chip";
                badge.textContent = permission;
                return badge;
              })
          );
          if (!permissions.size) {
            const empty = document.createElement("span");
            empty.className = "small text-muted";
            empty.textContent = "No permissions selected.";
            union.append(empty);
          }
        }
      };
      checkboxes.forEach((checkbox) =>
        checkbox.addEventListener("change", updateRoleSummary)
      );
      updateRoleSummary();
      editor.querySelector("[data-role-search]")?.addEventListener("input", (event) => {
        const query = event.target.value.trim().toLowerCase();
        cards.forEach((card) => {
          card.hidden =
            !!query &&
            !(card.dataset.roleSearchValue || "").toLowerCase().includes(query);
        });
      });
    });

    document.querySelector("[data-user-select-all]")?.addEventListener("click", () => {
      document
        .querySelectorAll("[data-user-selection] input.user-select:not(:disabled)")
        .forEach((checkbox) => {
          checkbox.checked = true;
        });
    });
    document
      .querySelector("[data-user-select-clear]")
      ?.addEventListener("click", () => {
        document
          .querySelectorAll("[data-user-selection] input.user-select")
          .forEach((checkbox) => {
            checkbox.checked = false;
          });
      });

    document
      .querySelector("[data-copy-credentials]")
      ?.addEventListener("click", async (event) => {
        const rows = Array.from(document.querySelectorAll("[data-credential-row]"));
        const value = rows
          .map((row) => {
            const email = row.querySelector("[data-credential-email]")?.textContent.trim();
            const password = row
              .querySelector("[data-credential-password]")
              ?.textContent.trim();
            return `${email}\t${password}`;
          })
          .join("\n");
        try {
          await navigator.clipboard.writeText(value);
          event.currentTarget.textContent = "Copied";
        } catch (_error) {
          window.prompt("Copy permission-test credentials", value);
        }
      });
  });
})();
