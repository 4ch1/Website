using System;
using System.Data.Common;
using System.Runtime.InteropServices;
using System.Security.Claims;
using System.Threading.Tasks;
using IIS.Models;
using IIS.Models.Authentication;
using IIS.Models.Exception;
using IIS.Queries;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Rendering;
using Microsoft.Extensions.Logging;
using NewMvcProject.Models;
using Newtonsoft.Json;

namespace IIS.Controllers
{
    [Route("authentication")]
    public class AuthenticationController : Controller
    {
        private readonly ILogger _logger;
        private readonly SessionManager _sessionManager;

        public AuthenticationController(ILogger<AuthenticationController> logger, SessionManager sessionManager)
        {
            _logger = logger;
            _sessionManager = sessionManager;
        }

        [HttpPost]
        public async Task<IActionResult> Login(Login formLogin)
        {
            var user = await AuthQueries.GetByEmail(formLogin.Email);
            if (user != null)
            {
                if (!string.IsNullOrEmpty(user.Password))
                {
                    if (user.Password.Equals(formLogin.Password))
                    {
                        StoreInfo(user);
                        return RedirectToAction("Index", "Home");
                    }
                }
            }

            _logger.LogError("The user with given email and password doesn't exist");

            var errorView = View();
            ModelState.AddModelError("Password", "The user with given email doesn't exist");
            errorView.StatusCode = 401;
            return errorView;
        }

        private void StoreInfo(ApplicationUser user)
        {
            _sessionManager.SignIn(user);
        }

        [HttpGet]
        public IActionResult Login()
        {
            return View();
        }

        [HttpGet]
        [Route("signup")]
        public IActionResult Sign_Up()
        {
            return View();
        }

        [HttpPost]
        [Route("signup")]
        public async Task<IActionResult> Sign_Up(ApplicationUser user)
        {
            await _sessionManager.CreateUser(user);
            _sessionManager.SignIn(user);
            return RedirectToAction("Index", "Home");
        }

        [HttpGet]
        [Route("list")]
        public async Task<IActionResult> GetAllEmails()
        {
            return Ok(JsonConvert.SerializeObject(await AuthQueries.GetAllEmails()));
        }
    }
}