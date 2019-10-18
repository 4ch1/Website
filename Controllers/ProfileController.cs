using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using IIS.Models.Tickets;
using IIS.Queries;
using Mailjet.Client;
using Mailjet.Client.Resources;
using Microsoft.AspNetCore.Mvc;
using NewMvcProject.Models;
using Newtonsoft.Json.Linq;

namespace IIS.Controllers
{
    [Route("profile")]
    public class ProfileController : Controller
    {
        private readonly SessionManager _sessionManager;
        private readonly CartManager _cartManager;

        public ProfileController(SessionManager sessionManager, CartManager cartManager)
        {
            _sessionManager = sessionManager;
            _cartManager = cartManager;
        }

        [HttpGet]
        [Route("current")]
        public IActionResult CurrentUser()
        {
            return View(_sessionManager.GetCurrentUser());
        }

        [HttpGet]
        [Route("logOut")]
        public IActionResult Log_OutAsync()
        {
            _sessionManager.SignOut(_sessionManager.GetCurrentUser());
            return RedirectToAction("Index", "Home");
        }

        [HttpGet]
        [Route("cart")]
        public async Task<IActionResult> Cart()
        {
            var applicationUser = _sessionManager.GetCurrentUser();

            return _cartManager.GetItemCount(applicationUser) == 0
                ? View(new List<Ticket>())
                : View(await TicketQueries.GetAllTickets(_cartManager.GetItems(applicationUser)));
        }

        [HttpPost]
        [Route("cart")]
        public async Task<IActionResult> Cart([FromForm] IEnumerable<long> id)
        {
            var user = _sessionManager.GetCurrentUser();
            _cartManager.AddItems(user, id);
            return View(await TicketQueries.GetAllTickets(_cartManager.GetItems(user)));
        }

        [HttpPost]
        [Route("buy")]
        public async Task<IActionResult> Buy([FromForm] IEnumerable<long> id, [FromForm] string Buy,
            [FromForm] string Delete)
        {
            var user = _sessionManager.GetCurrentUser();

            if (string.IsNullOrEmpty(Delete)) //Delete is null - buys
            {
                await SendEmail(user, "iiserver2018@mail.ru", ComposeMail(await TicketQueries.GetAllTickets(id.ToList())));
            }

            _cartManager.RemoveItems(user, id);
            return View("Cart", await TicketQueries.GetAllTickets(_cartManager.GetItems(user)));
        }

        private string ComposeMail(IEnumerable<Ticket> tickets)
        {
            var builder = new StringBuilder();
            builder.Append("<table style=\"font-family: arial, sans-serif;border-collapse: collapse;width: 100%;\">");
            builder.Append(@"<style>
                                td, th {
                                    border: 1px solid #dddddd;
                                    text-align: left;
                                    padding: 8px;
                                }
                           </style>");
            builder.Append("<thead>");
            builder.Append("<tr>");
            builder.Append("<th style=\"border: 1px solid #dddddd;text-align: left;padding: 8px;\">From airport</th>");
            builder.Append("<th style=\"border: 1px solid #dddddd;text-align: left;padding: 8px;\">To airport</th>");
            builder.Append("<th style=\"border: 1px solid #dddddd;text-align: left;padding: 8px;\">At time</th>");
            builder.Append("<th style=\"border: 1px solid #dddddd;text-align: left;padding: 8px;\">Company</th>");
            builder.Append("<th style=\"border: 1px solid #dddddd;text-align: left;padding: 8px;\">Category</th>");
            builder.Append("<th style=\"border: 1px solid #dddddd;text-align: left;padding: 8px;\">Price</th>");
            builder.Append("</tr>");
            builder.Append("</thead>");
            builder.Append("<tbody>");
            foreach (var ticket in tickets)
            {
                builder.Append("<tr>");
                builder.Append($"<td style=\"border: 1px solid #dddddd;text-align: left;padding: 8px;\">{ticket.FromAirport.Location} ( {ticket.FromAirport.FullName} )</td>");
                builder.Append($"<td style=\"border: 1px solid #dddddd;text-align: left;padding: 8px;\">{ticket.ToAirport.Location} ( {ticket.ToAirport.FullName} )</td>");
                builder.Append($"<td style=\"border: 1px solid #dddddd;text-align: left;padding: 8px;\">{ticket.Date}</td>");
                builder.Append($"<td style=\"border: 1px solid #dddddd;text-align: left;padding: 8px;\">{ticket.Company.FullName}</td>");
                builder.Append($"<td style=\"border: 1px solid #dddddd;text-align: left;padding: 8px;\">{ticket.Category.FullName}</td>");
                builder.Append($"<td style=\"border: 1px solid #dddddd;text-align: left;padding: 8px;\">{ticket.Price}$</td>");
                builder.Append("</tr>");
            }
            builder.Append("</tbody>");
            builder.Append("</table>");
            builder.Append($"<p>Whole sum: {tickets.Sum(ticket => ticket.Price)}$</p>");
            return builder.ToString();
        }

        private async Task SendEmail(ApplicationUser user, string email, string message)
        {
            var client = new MailjetClient("67b80ddfe90c0b05b2a415bd772d0170", "00619d65d8ab7e54ef5798ebdc5539b3")
            {
                Version = ApiVersion.V3_1
            };
            var request = new MailjetRequest
            {
                Resource = Send.Resource
            }
                .Property(Send.Messages, new JArray {
                    new JObject {
                        {"From", new JObject {
                            {"Email", email},
                            {"Name", "IIS Support"}
                        }},
                        {"To", new JArray {
                            new JObject {
                                {"Email", user.Email},
                                {"Name", $"{user.FirstName} {user.LastName}"}
                            }
                        }},
                        {"Subject", "New tickets"},
                        {"HtmlPart", message},
                    }
                });
            var response = await client.PostAsync(request);
            if (response.IsSuccessStatusCode)
            {
                Console.WriteLine("Total: {0}, Count: {1}\n", response.GetTotal(), response.GetCount());
                Console.WriteLine(response.GetData());
            }
            else
            {
                Console.WriteLine("StatusCode: {0}\n", response.StatusCode);
                Console.WriteLine("ErrorInfo: {0}\n", response.GetErrorInfo());
                Console.WriteLine(response.GetData());
                Console.WriteLine("ErrorMessage: {0}\n", response.GetErrorMessage());
            }
        }
    }
}