{ pkgs ? import <nixpkgs> { config.allowUnfree = true; } }:

pkgs.mkShell {
  nativeBuildInputs = with pkgs; [
    nodejs
    vscode
    playwright-driver.browsers
  ];

  shellHook = ''
    export PLAYWRIGHT_CHROMIUM_BIN="${pkgs.brave}/bin/brave"
  '';
}
