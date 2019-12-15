/* cc -Weverything -o full-disk-access full-disk-access.c
 * Work around MacOS Catalina's access restrictions.  Compile this, open System
 * Preference > Security & Privacy > Privacy, select Full Disk Access, add the
 * binary.  Now you should be able to wrap any command that needs full disk
 * access, e.g. "full-disk-access rsync -av ~/Documents/ backups:Documents/".
 */
#include <stdio.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>

int main(int argc __attribute__((unused)), char **argv) {
  pid_t pid = fork();
  if (pid == -1) {
    perror("fork() failed: ");
    exit(EXIT_FAILURE);
  }
  if (pid == 0) {
    execvp(argv[1], &argv[1]);
    exit(EXIT_FAILURE);
  }

  int exit_status;
  waitpid(pid, &exit_status, 0);
  if (WIFEXITED(exit_status)) {
    exit(WEXITSTATUS(exit_status));
  }
  if (WIFSIGNALED(exit_status)) {
    exit(WTERMSIG(exit_status));
  }
  fprintf(stderr, "Unexpected exit status from child command: %d\n",
          exit_status);
}
